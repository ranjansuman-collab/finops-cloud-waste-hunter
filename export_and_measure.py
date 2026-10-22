import os
import sys
import win32com.client

abs_docx = os.path.abspath("Cloud_Waste_Hunter_Project_Report.docx")
abs_pdf = os.path.abspath("Cloud_Waste_Hunter_Project_Report.pdf")

print("Initializing Word COM...", flush=True)
word = win32com.client.Dispatch("Word.Application")
word.Visible = False
word.DisplayAlerts = 0

try:
    print(f"Opening DOCX: {abs_docx}", flush=True)
    doc = word.Documents.Open(abs_docx, ReadOnly=True)
    
    print(f"Exporting to PDF: {abs_pdf}", flush=True)
    doc.SaveAs(abs_pdf, FileFormat=17) # 17 is wdFormatPDF
    
    pages = doc.ComputeStatistics(2) # 2 is wdStatisticPages
    words = doc.ComputeStatistics(0) # 0 is wdStatisticWords
    
    print("=== EXPORT SUCCESS ===", flush=True)
    print("DOCX Path:", abs_docx, flush=True)
    print("PDF Path:", abs_pdf, flush=True)
    print("Page Count:", pages, flush=True)
    print("Word Count:", words, flush=True)
finally:
    try:
        doc.Close(False)
    except Exception:
        pass
    try:
        word.Quit()
    except Exception:
        pass
    print("Word COM process closed cleanly.", flush=True)
