from __future__ import annotations
from datetime import date
from decimal import Decimal
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .services import SENDER, Totals, indian_words

ROOT = Path(__file__).resolve().parents[2]; ASSETS = ROOT / "assets"
PURPLE, BLUE, GREEN = colors.HexColor("#532052"), colors.HexColor("#8cd4ec"), colors.HexColor("#dbead3")
def _money(v: Decimal) -> str: return f"INR {v:,.2f}"
def _background(c, _):
    c.saveState(); w,h=A4; letter=ASSETS / "Letter_Head.png"
    if letter.exists(): c.drawImage(str(letter),0,0,width=w,height=h)
    c.setFillColor(colors.Color(.35,.2,.4,alpha=.09)); c.setFont("Helvetica-Bold",48); c.drawCentredString(w/2,h/2,"HADS"); c.restoreState()
def _p(text, style): return Paragraph(str(text).replace("\n","<br/>"),style)
def _party(client, style):
    def block(label, x): return _p(f"<b>{label}</b><br/><b>{x['name']}</b><br/>{x['address']}<br/>Contact Person: {x.get('contact_person','')}<br/>Mobile Number: {x.get('mobile','')}<br/>GSTIN: {x['gstin']}",style)
    return Table([[block("From,",SENDER),block("Bill to,",client)]],colWidths=[85*mm,85*mm],style=[("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0)])

def generate_document(*, kind: str, client: dict, issue_date: date, subject: str, totals: Totals, output: Path, number: str|None=None, original_invoice: str|None=None, original_date: date|None=None) -> Path:
    if output.exists(): raise FileExistsError(f"Document already exists: {output}")
    output.parent.mkdir(parents=True,exist_ok=True); styles=getSampleStyleSheet(); normal=ParagraphStyle("doc",parent=styles["Normal"],fontSize=7.5,leading=10); title=ParagraphStyle("title",parent=styles["Title"],fontSize=12,alignment=1,fontName="Helvetica-Bold")
    meta=f"Date: {issue_date:%d-%m-%Y}"+(f"<br/>Invoice number: {number}" if number and kind=="TAX INVOICE" else "")
    elements=[Spacer(1,48*mm),Paragraph(kind,title),Spacer(1,8*mm),Table([["",_p(meta,normal)]],colWidths=[115*mm,55*mm]),Spacer(1,5*mm),_party(client,normal),Spacer(1,5*mm),_p(f"<b>SUBJECT:</b><br/>{subject}",normal),Spacer(1,7*mm)]
    if kind=="CREDIT NOTE":
        info=[["Credit Note No.",number,"Credit Note Date",issue_date.strftime("%d/%m/%Y")],["Original Invoice No.",original_invoice,"Original Invoice Date",original_date.strftime("%d/%m/%Y")]]
        t=Table(info,colWidths=[37*mm,43*mm,42*mm,48*mm]); t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.5,colors.black),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#d9edf7")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#d9edf7")),("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("ALIGN",(0,0),(-1,-1),"CENTER")]))
        elements += [t,Spacer(1,6*mm),_p("<b>Credit note particulars</b>",normal),Spacer(1,2*mm)]
        rows=[["Description","Taxable / Tax Rate","Amount (INR)"],["Taxable value reversed","—",_money(totals.taxable)],["CGST","9%",_money(totals.cgst)],["SGST","9%",_money(totals.sgst)],["Total GST","18%",_money(totals.total_gst)],["Total credit note value","",_money(totals.total)]]
    else:
        rows=[["Items & Description","Quantity","Price in INR"],["Services / Goods as per PO","1",_money(totals.taxable)],["SGST/UGST 9%","",_money(totals.sgst)],["CGST 9%","",_money(totals.cgst)],["TOTAL GST","",_money(totals.total_gst)],["TOTAL AMOUNT","",_money(totals.total)]]
    table=Table(rows,colWidths=[92*mm,25*mm,53*mm],rowHeights=[8*mm]+[8*mm]*(len(rows)-1)); cmds=[("GRID",(0,0),(-1,-1),.5,colors.black),("BACKGROUND",(0,0),(-1,0),BLUE),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,-2),(-1,-1),"Helvetica-Bold"),("ALIGN",(0,0),(0,-1),"LEFT"),("ALIGN",(1,0),(1,-1),"CENTER"),("ALIGN",(2,0),(2,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("FONTSIZE",(0,0),(-1,-1),8),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5)]
    if kind=="CREDIT NOTE": cmds += [("BACKGROUND",(0,-1),(-1,-1),GREEN)]
    table.setStyle(TableStyle(cmds)); elements += [table,Spacer(1,4*mm),_p(f"<b>Amount in Words:</b><br/>{indian_words(totals.total)}", normal),Spacer(1,8*mm)]
    sig=ASSETS / "Signature.png"; signature=[Image(str(sig),width=24*mm,height=11*mm)] if sig.exists() else []
    signature += [_p("Designated Partner<br/><br/>Name: Hemalatha M<br/>Designation: Managing Director",normal)]
    elements += [Table([["",signature]],colWidths=[115*mm,55*mm],style=[("VALIGN",(0,0),(-1,-1),"TOP")])]
    SimpleDocTemplate(str(output),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=10*mm,bottomMargin=18*mm).build(elements,onFirstPage=_background,onLaterPages=_background)
    return output
