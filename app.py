from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from supabase import create_client, Client
from io import BytesIO
from datetime import datetime
import os

# Criar app FastAPI
app = FastAPI(
    title="Supabase PDF Report Generator",
    description="API para gerar relatórios PDF a partir de dados do Supabase",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ReportRequest(BaseModel):
    table_name: str
    fields: List[str]
    supabase_url: str
    anon_key: str
    report_title: Optional[str] = None

def create_apple_style_pdf(data: List[dict], fields: List[str], title: str) -> BytesIO:
    """Cria um PDF com estilo minimalista inspirado na Apple"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           rightMargin=50, leftMargin=50,
                           topMargin=50, bottomMargin=50)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilo do título (Apple-like)
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#1d1d1f'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Estilo da data
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#86868b'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    
    # Adicionar título
    title_text = title if title else "Relatório de Dados"
    elements.append(Paragraph(title_text, title_style))
    
    # Adicionar data
    current_date = datetime.now().strftime("%d de %B de %Y")
    elements.append(Paragraph(current_date, date_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Preparar dados da tabela
    if not data:
        no_data_style = ParagraphStyle(
            'NoData',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#86868b'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Nenhum dado encontrado", no_data_style))
    else:
        # Cabeçalhos
        table_data = [[Paragraph(f"<b>{field}</b>", styles['Normal']) 
                      for field in fields]]
        
        # Dados
        for row in data:
            table_row = []
            for field in fields:
                value = str(row.get(field, ''))
                if len(value) > 50:
                    value = value[:47] + '...'
                table_row.append(Paragraph(value, styles['Normal']))
            table_data.append(table_row)
        
        # Criar tabela
        col_widths = [A4[0] / len(fields) - 1.2*inch/len(fields)] * len(fields)
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Estilo Apple: limpo, minimalista, com linhas sutis
        table.setStyle(TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1d1d1f')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            
            # Corpo
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1d1d1f')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            
            # Bordas sutis
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#d2d2d7')),
            ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e5e5e7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
    
    # Adicionar rodapé
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#86868b'),
        alignment=TA_CENTER
    )
    footer_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
    elements.append(Paragraph(footer_text, footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.get("/")
async def root():
    """Endpoint raiz - informações da API"""
    return {
        "message": "API de Geração de Relatórios PDF com Supabase",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoint": "POST /generate-report"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/generate-report")
async def generate_report(request: ReportRequest):
    """
    Gera um relatório PDF com dados do Supabase
    
    - **table_name**: Nome da tabela no Supabase
    - **fields**: Lista de campos a serem incluídos no relatório
    - **supabase_url**: URL do projeto Supabase
    - **anon_key**: Chave anon do Supabase
    - **report_title**: Título opcional do relatório
    """
    try:
        # Conectar ao Supabase
        supabase: Client = create_client(request.supabase_url, request.anon_key)
        
        # Buscar dados
        response = supabase.table(request.table_name).select(','.join(request.fields)).execute()
        
        if not response.data:
            data = []
        else:
            data = response.data
        
        # Gerar PDF
        pdf_buffer = create_apple_style_pdf(
            data, 
            request.fields,
            request.report_title or f"Relatório - {request.table_name}"
        )
        
        # Retornar PDF
        filename = f"relatorio_{request.table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {str(e)}")

# Para desenvolvimento local
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
