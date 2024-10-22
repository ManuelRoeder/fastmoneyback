import PIL.Image
from pypdf import PdfReader, PdfWriter
import tabula
#from tabulate import tabulate
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
import sys
import re
import numpy as np
#import pandas

import warnings
warnings.filterwarnings("ignore")

# Read pdf into list of DataFrame
FALLBACK_INBOX = "inbox"
OUTBOX = "outbox"

# UEK
UEKOSTEN_STR = "ÜK-Tag"
PKW_MULTI = 0.30
PKW_MULT_TRIFTIG = 0.40

def find_kosten_index(table):
    index = np.where(table == UEKOSTEN_STR)[1][0]
    return index

def get_number(inputString):
    return re.findall("\d+\.\d+", inputString)

def has_numbers(inputString):
    return any(char.isdigit() for char in inputString)

def clean_output_folder():
    out_dir = os.path.join(get_script_dir(), OUTBOX)
    files_to_del = [f for f in os.listdir(out_dir) if "antrag_abschlag" not in f]
    for file in files_to_del:
        filepath = os.path.join(out_dir, file)
        print("Cleaning file " + file)
        os.remove(filepath)

def get_script_dir():
    # scan for belege und rechnungen
    try:
        # Get the directory of the current script
        script_directory = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # Fallback to the current working directory if __file__ is not defined
        script_directory = os.getcwd()
    return script_directory


def check_folder(dropped_folder):
    antragsfile = [f for f in os.listdir(dropped_folder) if f.endswith('.pdf') and "Abrechnungsantrag" in f]
    if len(antragsfile) != 1:
        print("No Antrag found or too many Anträge in folder")
        sys.exit()
    return os.path.join(dropped_folder, antragsfile[0])


def convert_pngs(png_files_to_convert, droppedFolder):
    for png in png_files_to_convert:
        # do the conversion
        in_file = os.path.join(droppedFolder, png)
        out_fn = png.replace("png", "pdf")
        merged_png_path = os.path.join(droppedFolder, out_fn)
        if not os.path.exists(merged_png_path):
            # convert
            im = Image.open(in_file)
            image_rgb = im.convert("RGB")
            image_rgb.save(merged_png_path, "PDF", quality=100)
            print("Coverted image: " + png + " to " + merged_png_path)
        

# Append other PDFs to the initial PDF
def append_pdfs(base_pdf_path, pdfs_to_append, folder, antragsnummer):
    pdf_writer = PdfWriter()

    # Read the base PDF
    base_pdf = PdfReader(base_pdf_path)
    for page_num in range(len(base_pdf.pages)):
        pdf_writer.add_page(base_pdf.pages[page_num])

    # Append other PDFs
    for pdf_path in pdfs_to_append:
        pdf_reader = PdfReader(os.path.join(folder, pdf_path))
        for page_num in range(len(pdf_reader.pages)):
            pdf_writer.add_page(pdf_reader.pages[page_num])

    # Save the merged PDF
    final_filename = "antrag_abschlag_" + str(antragsnummer) + ".pdf"
    merged_pdf_path = os.path.join(get_script_dir(), OUTBOX, final_filename)
    with open(merged_pdf_path, 'wb') as out_pdf:
        pdf_writer.write(out_pdf)

    print(f"PDFs have been merged into {merged_pdf_path}")
    

def add_to_text_stream(stream, new_text):
    return stream + new_text + "\n"


def generate_stamp(data):
    script_directory = get_script_dir()
    # Load the image
    image = Image.open(os.path.join(script_directory, "templates", "stamp_blank.jpg"))
    # Create a drawing context
    draw = ImageDraw.Draw(image)

    # first line: kapitel, titel, festlegung
    pos_kapitel = (120, 65)
    pos_titel = (450, 65)
    #pos_festlegung = (860, 65)
    
    pos_proj = (350, 120)
    pos_art = (350, 175)
    pos_kst = (350, 260)
    pos_koa = (75, 335)
    pos_jahr = (180, 440)
    pos_datum = (120, 490)
    pos_abschlag = (420, 360)
    
    pos_x = (620, 540)
    
    # draw
    font = ImageFont.truetype("arial.ttf", 26)
    
    draw.text(pos_kapitel, str(data[0]), font=font, fill="black")
    draw.text(pos_titel, str(data[1]), font=font, fill="black")
    #draw.text(pos_festlegung, str(data[2]), font=font, fill="black")
    
    draw.text(pos_proj, str(data[2]), font=font, fill="black")
    draw.text(pos_art, str(data[3]), font=font, fill="black")
    draw.text(pos_kst, str(data[4]), font=font, fill="black")
    
    
    draw.text(pos_koa, str(data[5]), font=font, fill="black")
    draw.text(pos_jahr, str(2024), font=font, fill="black")
    draw.text(pos_datum, str(data[6]), font=font, fill="black")
    draw.text(pos_abschlag, data[7], font=font, fill="black")
    
    draw.text(pos_x, "X", font=font, fill="black")

    path = os.path.join(script_directory, OUTBOX, "output.jpg")
    # Save or display the modified image
    image.save(path)
    return path

def main(droppedFolder):
    print("Fast Money Back - Scanning folder: " + droppedFolder)
    path_to_antrag = check_folder(droppedFolder)
    
    # parse doc
    tables = tabula.read_pdf(path_to_antrag, stream=True, lattice=True, pages="all", multiple_tables=True)
    if tables is None:
        print("Could not parse Antrag")
        sys.exit()
    
    # initial user queries
    percent_cashback = float(input("Prozentsatz Abschlagszahlung(0.0 - 1.0):"))
    while percent_cashback > 1.0 or percent_cashback <= 0.0:
        print("Eingabe ungültig")
        percent_cashback = float(input("Prozentsatz Abschlagszahlung(0.0 - 1.0):"))
    sachbearbeiterin = input("Sachbearbeiter*in bei HSFI, leer für 'Reisekostenstelle':")
    belege_gesamt = input("Gesamtbetrag lt. Belege in Euro ('12345.00'), leer für Belege-Check:")
    if belege_gesamt == "":
        belege_check_auto = True
        print("Automatischer Belege-Check aktiviert")
    else:  
        belege_gesamt = float(belege_gesamt)
        belege_check_auto = False

    # receiver
    to_str = ""
    to_str = add_to_text_stream(to_str, "Hochschulservice Finanzen")
    if sachbearbeiterin != "":
        to_str = add_to_text_stream(to_str, "z.H. " + sachbearbeiterin)
    to_str = add_to_text_stream(to_str, "Ignatz-Schön-Str. 11")
    to_str = add_to_text_stream(to_str, "97421 Schweinfurt")
    
    # pkw fahrt
    pkw_fahrt = False
    pkw_kosten = 0.0

    ######## parsing starts here ##########
    header_data_table = None
    sender_data_table = None
    buchungsdaten_table1 = None
    buchungsdaten_table2 = None
    hauptreisedaten_table = None
    verkehrsmittel_table = None
    verkehrsmittel_table_2 = None
    nebenkosten_table = None
    for i, table in enumerate(tables):
        #print(table.keys)
        #print(f"Table {i + 1}")
        try:
            #if "Antragsnummer" in table.iloc[0,0]:
            if "Antragsnummer" in table.columns[0]:
                header_data_table = table
                continue
        except:
            pass
        
        try:
            #if "PLZ" in table.iloc[1,0]:
            if "Antragstellerdaten" in table.columns[0]:
                sender_data_table = table
                continue
        except:
            pass
        
        try:
            #if "Kapitel" in table.iloc[0,0] and "Titel" in table.iloc[0,0]:
            if "Buchungsdaten" in table.columns[0] and not "zusätzliche" in table.columns[0]:
                buchungsdaten_table1 = table
                continue
        except:
            pass
        
        try:
            #if "Verfahren" in table.iloc[0,0]:
            if "KLR-Daten" in table.columns[0] and not "zusätzliche" in table.columns[0]:
                buchungsdaten_table2 = table
                continue
        except:
            pass
        
        try:
            #if "Hauptreisedaten" in table.iloc[0,0]:
            if "Hauptreisedaten" in table.columns[0] and not "zusätzliche" in table.columns[0]:
                hauptreisedaten_table = table
                continue
        except:
            pass
        
        try:
            #if "Hauptreisedaten" in table.iloc[0,0]:
            if "Verkehrsmittel" in table.columns[0] and not "zusätzliche" in table.columns[0]:
                verkehrsmittel_table = table
                # lookahead
                forthcoming_table = tables[i+1]
                if not "Mitreisende" in forthcoming_table.columns[0]:
                    verkehrsmittel_table_2 = forthcoming_table
                    # If you want the first row back as data
                    verkehrsmittel_table_2.loc[-1] = verkehrsmittel_table_2.columns  # Append the original header as a new row
                    verkehrsmittel_table_2.index = verkehrsmittel_table_2.index + 1  # Shift index
                    verkehrsmittel_table_2 = verkehrsmittel_table_2.sort_index()  
                continue
        except:
            pass
        
        try:
            #if "Hauptreisedaten" in table.iloc[0,0]:
            if "Nebenkosten" in table.columns[0] and not "zusätzliche" in table.columns[0]:
                nebenkosten_table = table
                continue
        except:
            pass


    headline_str = ""
    if header_data_table is not None:
        antragsnummer = header_data_table.iloc[1,0]
        antragsdatum = header_data_table.iloc[1,1]
        reisezusammenfassung = header_data_table.iloc[3,0]
        genehmigungsnummer = header_data_table.iloc[3,1]
        header_str = add_to_text_stream(headline_str, "Antrag auf Abschlagszahlung für die Reise mit der Genehmigungsnummer " + genehmigungsnummer)

    sender_str = ""
    name_2 = sender_data_table.iloc[0,1]
    name_1 = sender_data_table.iloc[0, (sender_data_table.shape[1] - 1)]
    name = name_1 + " " + name_2
    tel = sender_data_table.iloc[6,1]
    mail = sender_data_table.iloc[6,2]
    personalnummer = sender_data_table.iloc[6,3]
    sender_str = add_to_text_stream(sender_str, name)
    sender_str = add_to_text_stream(sender_str, "Pers.Nr.: " + personalnummer)
    sender_str = add_to_text_stream(sender_str, "Tel: " + tel)
    sender_str = add_to_text_stream(sender_str, "Mail: " + mail)
        
    if buchungsdaten_table1 is not None:
        kapitel = buchungsdaten_table1.iloc[1,0]
        titel = buchungsdaten_table1.iloc[1,1]
        ebene1 = buchungsdaten_table1.iloc[1,5]
        ebene2 = buchungsdaten_table1.iloc[1,6]
        
    if buchungsdaten_table2 is not None:
        kostenart = buchungsdaten_table2.iloc[1,2]
        kostenstelle = buchungsdaten_table2.iloc[1,3]

    if belege_check_auto:
        ########################### Belege-Check ############################
        if hauptreisedaten_table is not None:
            print("Belege-Check Hauptreisedaten")
            # kostenindex
            START_INDEX_Y_TAG = 0
            START_INDEX_Y_KOSTEN = find_kosten_index(hauptreisedaten_table)
            rolling_index = 3
            reisetage = list()
            while rolling_index < 100:
                try:
                    if not hauptreisedaten_table.isnull().iloc[rolling_index,START_INDEX_Y_TAG] and not hauptreisedaten_table.isnull().iloc[rolling_index,START_INDEX_Y_KOSTEN]:
                        tag = hauptreisedaten_table.iloc[rolling_index, START_INDEX_Y_TAG]
                        kosten = hauptreisedaten_table.iloc[rolling_index, START_INDEX_Y_KOSTEN]
                        reisetage.append((tag, kosten))
                    rolling_index = rolling_index + 1
                except IndexError:
                    break
        
            kosten_reisetage = 0.0
            print("Beleg vorhanden für Reisetage? (leer für JA, n für NEIN)")
            idx_to_rem = list()
            for idx, tag in enumerate(reisetage):
                user_input = input("DATUM: " + tag[0] + " | KOSTEN: " + tag[1] + "|  ")
                if user_input != "":
                    idx_to_rem.append(idx)
                else:
                    kosten_reisetage = kosten_reisetage + float(get_number(tag[1])[0])
                    #reisetage[idx][1] = 0.0
            # rem
            for index in sorted(idx_to_rem, reverse=True):
                reisetage.pop(index)
            
            
            
        if verkehrsmittel_table is not None:
            print("Belege-Check Verkehrsmittel")
            # kostenindex
            START_INDEX_Y_TAG = 0
            START_INDEX_Y_KOSTEN = 8
            rolling_index = 1
            verkehrsmittel = list()
            kosten_verkehrsmittel = 0.0
            pkw_triftig = False
            while rolling_index < 100:
                try:
                    if not verkehrsmittel_table.isnull().iloc[rolling_index,START_INDEX_Y_TAG] and not verkehrsmittel_table.isnull().iloc[rolling_index,START_INDEX_Y_KOSTEN] and has_numbers(verkehrsmittel_table.iloc[rolling_index, START_INDEX_Y_KOSTEN]):
                        tag = verkehrsmittel_table.iloc[rolling_index, START_INDEX_Y_TAG] + " " + verkehrsmittel_table.iloc[rolling_index, START_INDEX_Y_TAG + 1]
                        tag = tag.replace('\r', ' ')
                        if "PKW" in tag:
                            km = float(verkehrsmittel_table.iloc[rolling_index, START_INDEX_Y_KOSTEN - 1].strip(" km"))
                            if "triftig" in tag:
                                pkw_triftig = True 
                                kosten = str(km * PKW_MULT_TRIFTIG) + " EUR (triftiger Grund)"
                                kosten = kosten.replace('\r', ' ')
                                print("Triftige PKW-Fahrt entdeckt, Kosten berechnet: " + str(km) + "(KM) * " + str(PKW_MULT_TRIFTIG) + " = " + str(kosten))
                            else:
                                kosten = str(km * PKW_MULTI) + " EUR"
                                kosten = kosten.replace('\r', ' ')
                                print("PKW-Fahrt entdeckt, Kosten berechnet: " + str(km) + "(KM) * " + str(PKW_MULTI) + " = " + str(kosten))
                        else:    
                            kosten = verkehrsmittel_table.iloc[rolling_index, START_INDEX_Y_KOSTEN]
                            kosten = kosten.replace('\r', ' ')
                        verkehrsmittel.append((tag, str(kosten)))
                    rolling_index = rolling_index + 1
                except IndexError:
                    print("IndexError at verkehrsmittel_table_1")
                    break
                
        if verkehrsmittel_table_2 is not None:
            #print("Belege-Check Verkehrsmittel")
            # kostenindex
            START_INDEX_Y_TAG_2 = 0
            START_INDEX_Y_KOSTEN_2 = (verkehrsmittel_table_2.shape[1] - 2)
            rolling_index = 0
            #verkehrsmittel = list()
            #kosten_verkehrsmittel = 0.0
            #pkw_triftig = False
            while rolling_index < 100:
                try:
                    if not verkehrsmittel_table_2.isnull().iloc[rolling_index,START_INDEX_Y_TAG_2] and not verkehrsmittel_table_2.isnull().iloc[rolling_index,START_INDEX_Y_KOSTEN_2] and has_numbers(verkehrsmittel_table_2.iloc[rolling_index, START_INDEX_Y_KOSTEN_2]):
                        tag = verkehrsmittel_table_2.iloc[rolling_index, START_INDEX_Y_TAG_2] + " " + verkehrsmittel_table_2.iloc[rolling_index, START_INDEX_Y_TAG_2+1]
                        tag = tag.replace('\r', ' ')
                        if "PKW" in tag:
                            km = float(verkehrsmittel_table_2.iloc[rolling_index, START_INDEX_Y_KOSTEN_2 - 1].strip(" km"))
                            if "triftig" in tag:
                                pkw_triftig = True 
                                kosten = str(km * PKW_MULT_TRIFTIG) + " EUR (triftiger Grund)"
                                kosten = kosten.replace('\r', ' ')
                                print("Triftige PKW-Fahrt entdeckt, Kosten berechnet: " + str(km) + "(KM) * " + str(PKW_MULT_TRIFTIG) + " = " + str(kosten))
                            else:
                                kosten = str(km * PKW_MULTI) + " EUR"
                                kosten = kosten.replace('\r', ' ')
                                print("PKW-Fahrt entdeckt, Kosten berechnet: " + str(km) + "(KM) * " + str(PKW_MULTI) + " = " + str(kosten))
                        else:    
                            kosten = verkehrsmittel_table_2.iloc[rolling_index, START_INDEX_Y_KOSTEN_2]
                            kosten = kosten.replace('\r', ' ')
                        verkehrsmittel.append((tag, str(kosten)))
                    rolling_index = rolling_index + 1
                except IndexError:
                    print("IndexError at verkehrsmittel_table_2")
                    break
            
        print("Beleg vorhanden für Verkehrsmittel? (leer für JA, n für NEIN)")
        idx_to_rem = list()
        for idx, tag in enumerate(verkehrsmittel):
            user_input = input("DATUM: " + tag[0] + " | KOSTEN: " + tag[1] + "|  ")
            if user_input != "":
                idx_to_rem.append(idx)
            else:
                if "PKW" in tag[0]:
                    pkw_fahrt = True
                    pkw_kosten = pkw_kosten + float(get_number(tag[1])[0])
                kosten_verkehrsmittel = kosten_verkehrsmittel + float(get_number(tag[1])[0])
        
        for index in sorted(idx_to_rem, reverse=True):
            verkehrsmittel.pop(index)
        
        
        if nebenkosten_table is not None:
            print("Belege-Check Nebenkosten")
            # kostenindex
            START_INDEX_Y_TAG = 0
            START_INDEX_Y_TYP = 1
            START_INDEX_Y_KOSTEN = 2
            rolling_index = 1
            nebenkosten = list()
            kosten_nebenkosten = 0.0
            while rolling_index < 100:
                try:
                    if not nebenkosten_table.isnull().iloc[rolling_index,START_INDEX_Y_TYP] and not nebenkosten_table.isnull().iloc[rolling_index,START_INDEX_Y_TAG] and not nebenkosten_table.isnull().iloc[rolling_index,START_INDEX_Y_KOSTEN] and has_numbers(nebenkosten_table.iloc[rolling_index, START_INDEX_Y_KOSTEN]):
                        kosten = nebenkosten_table.iloc[rolling_index, START_INDEX_Y_KOSTEN]
                        typ = nebenkosten_table.iloc[rolling_index, START_INDEX_Y_TYP]
                        tag = nebenkosten_table.iloc[rolling_index, START_INDEX_Y_TAG]
                        total = tag + " " + typ
                        nebenkosten.append((total, kosten))
                    rolling_index = rolling_index + 1
                except IndexError:
                    break
            
            print("Beleg vorhanden für Nebenkosten? (leer für JA, n für NEIN)")
            idx_to_rem = list()
            for idx, tag in enumerate(nebenkosten):
                user_input = input("DATUM: " + tag[0] + " | KOSTEN: " + tag[1] + "|  ")
                if user_input != "":
                    idx_to_rem.append(idx)
                else:
                    kosten_nebenkosten = kosten_nebenkosten + float(get_number(tag[1])[0])
                
            for index in sorted(idx_to_rem, reverse=True):
                nebenkosten.pop(index)
                
        
        user_input = input("Einmalige Kosten bei Übernachtung (leer für NEIN, j für JA)?")
        if user_input == "j":
            reason_add = input("Beschreibung Kostenpunkt:")
            cost_add = input("Betrag im Format 123.50:")
            cost_add = float(cost_add)
            kosten_reisetage = kosten_reisetage + cost_add
            print("Der Betrag für " + reason_add + "(" + str(cost_add) + " Euro)" + " wurde zum Gesamtbetrag der Reisekosten addiert.")
        
        print("Gesamtkosten laut Belegen:")
        print("Übernachtungskosten: " + str(kosten_reisetage))
        print("Verkehrsmittel: " + str(kosten_verkehrsmittel))
        print("Nebenkosten: " + str(kosten_nebenkosten))
        print("----------------------")
        belege_gesamt = kosten_nebenkosten + kosten_verkehrsmittel + kosten_reisetage
        print("TOTAL: " + str(belege_gesamt))
        #####################################################################

        
        
    # format numbers
    abschlag = belege_gesamt * percent_cashback
    abschlag_str = ("%.2f" % abschlag)
    belege_gesamt_str = ("%.2f" % belege_gesamt)
    percent_cashback_str = ("%.0f" % (percent_cashback * 100))

    greetings_str= ""
    greetings_str = add_to_text_stream(greetings_str, "Sehr geehrte Damen und Herren,")

    main_txt_str = ""
    main_txt_str = add_to_text_stream(main_txt_str, "für meine " + reisezusammenfassung + " (GN-Nr." + genehmigungsnummer + ") stelle ich hiermit ")
    main_txt_str = add_to_text_stream(main_txt_str,"einen Antrag auf Abschlagszahlung zu " + percent_cashback_str + " Prozent der angefügten Rechnungen und Belege.")
                                      
    if pkw_fahrt:
        pkw_kosten_str = ("%.2f" % pkw_kosten)
        pkw_multi_str = ("%.0f" % (pkw_kosten/PKW_MULTI)) if not pkw_triftig else ("%.0f" % (pkw_kosten/PKW_MULT_TRIFTIG))
        pkw_calc_str = str(PKW_MULTI) + " x " + pkw_multi_str + " km" if not pkw_triftig else str(PKW_MULT_TRIFTIG) + " x " + pkw_multi_str + " km"
        main_txt_str = add_to_text_stream(main_txt_str, "Die Berechnung enthält angefallene PKW-Kosten in Höhe von " + pkw_kosten_str + " Euro (" + pkw_calc_str + ")." )
    main_txt_str = add_to_text_stream(main_txt_str, "Der Gesamtbetrag beläuft sich insgesamt auf " + belege_gesamt_str + " Euro.")
    main_txt_str = add_to_text_stream(main_txt_str, "Somit ergibt sich eine Abschlagszahlung von " + str(abschlag_str) + " Euro.")
    main_txt_str = add_to_text_stream(main_txt_str, "Zur Erleichterung der Bearbeitung habe ich den zugehörigen Abrechnungsantrag angehängt.")



    finish_str = ""
    finish_str = add_to_text_stream(finish_str, "Mit freundlichen Grüßen")
    finish_str = add_to_text_stream(finish_str, name)

    appendix_str = ""
    appendix_str = add_to_text_stream(appendix_str, "Anbei:")

    # Scan for PDF files
    pdf_files = [f for f in os.listdir(droppedFolder) if f.endswith('.pdf')]
    antrags_datei = ""
    for file in pdf_files:
        if "Abrechnungsantrag" in file:
            antrags_datei = file
            continue
        appendix_str = add_to_text_stream(appendix_str, "   - " + file.strip(".pdf"))
    appendix_str = add_to_text_stream(appendix_str, "   - " + antrags_datei.strip(".pdf"))
    #print(appendix_str)

    datum_heute = datetime.now().date()
    finance_data = (kapitel, titel, ebene1, ebene2, kostenstelle, kostenart, datum_heute, abschlag_str)
    path_to_tmp_stamp = generate_stamp(finance_data)

    # create ouitput pdf file
    script_directory = get_script_dir()
    image = Image.open(path_to_tmp_stamp)
    image_rgb = image.convert('RGB')
    image_rgb_path = os.path.join(script_directory, OUTBOX, 'temp_image.jpg')
    image_rgb.save(image_rgb_path)

    # Create a new PDF document
    pdf = FPDF()
    pdf.add_page()

    # Get the dimensions of the image
    image_width, image_height = image.size
    image_width_mm = image_width * 0.264583 * 0.4  # Convert pixels to mm (assuming 96 dpi)
    image_height_mm = image_height * 0.264583 * 0.4  # Convert pixels to mm (assuming 96 dpi)

    # Define the position where you want to place the image (bottom-left corner)
    stamp_pos = (80, 200) # 

    # Insert the image into the PDF at the specified position
    pdf.image(image_rgb_path, x=stamp_pos[0], y=stamp_pos[1], w=image_width_mm, h=image_height_mm)

    # Add text to the PDF
    pdf.set_font("Arial", size=10)

    pdf.set_xy(10, 10)
    pdf.multi_cell(0, 5, to_str)

    pdf.set_xy(140, 10)
    pdf.multi_cell(0, 5, sender_str)

    pdf.set_font("Arial", size=10, style='B')
    pdf.set_xy(10, 55)
    pdf.cell(0, 5, header_str)

    pdf.set_font("Arial", size=10)
    pdf.set_xy(10, 70)
    pdf.multi_cell(0, 5, greetings_str)

    pdf.set_xy(10, 80)
    pdf.multi_cell(0, 5, main_txt_str)

    pdf.set_xy(10, 120)
    pdf.multi_cell(0, 5, finish_str)

    pdf.set_xy(10, 140)
    pdf.multi_cell(0, 5, appendix_str)


    # Save the PDF document
    pdf_output_path = os.path.join(script_directory, OUTBOX, 'output.pdf')
    
    pdf.output(pdf_output_path)
    
    #convert pngs to pdfs
    png_files_to_convert = [f for f in os.listdir(droppedFolder) if f.endswith('.png')]
    convert_pngs(png_files_to_convert, droppedFolder)
    
    pdf_files_to_append = [f for f in os.listdir(droppedFolder) if f.endswith('.pdf')]
    # append antrag at the end
    append_pdfs(pdf_output_path, pdf_files_to_append, droppedFolder, genehmigungsnummer)
    

    
    # cleanup
    clean_output_folder()
    
    print("Fertig, noch 4 Schritte:")
    print("1) Antrag von Budgetverantwortlichem unterschreiben lassen")
    print("2) Antrag via Hauspost an Reisekostenstelle schicken")
    print("3) ...")
    print("4) Profit")



if __name__ == "__main__":
    try:
        droppedFolder = sys.argv[1]
    except IndexError:
        print("No folder dropped")
        sys.exit()
        
    # create out dir
    out_dir = os.path.join(get_script_dir(), OUTBOX)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    main(droppedFolder)