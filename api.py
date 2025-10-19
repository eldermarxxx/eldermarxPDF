from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from supabase import create_client
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

def sanitize_text(text):
    """Remove caracteres especiais que podem causar problemas no PDF"""
    if text is None:
        return ""
    text = str(text)
    # Remove ou substitui caracteres problemáticos
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return text

def format_value(value):
    """Formata valores para exibição no PDF"""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        # Trunca textos muito longos
        if len(value) > 100:
            return value[:97] + "..."
        return value
    return str(value)

def create_pdf(data, table_name, fields):
    """Cria um PDF elegante com os dados"""
    buffer = io.BytesIO()
    
    # Configurar documento (paisagem se houver muitos campos)
    pagesize = landscape(A4) if len(fields) > 5 else A4
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, 
                           topMargin=1.5*cm, bottomMargin=1.5*cm,
                           leftMargin=2*cm, rightMargin=2*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para o título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulo
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    # Título
    title = Paragraph(f"Relatório: {sanitize_text(table_name)}", title_style)
    elements.append(title)
    
    # Data de geração
    date_text = f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
    subtitle = Paragraph(date_text, subtitle_style)
    elements.append(subtitle)
    elements.append(Spacer(1, 0.5*cm))
    
    # Preparar dados da tabela
    if not data:
        no_data = Paragraph("Nenhum dado encontrado.", styles['Normal'])
        elements.append(no_data)
    else:
        # Cabeçalhos
        headers = [sanitize_text(field).upper() for field in fields]
        table_data = [headers]
        
        # Dados
        for row in data:
            row_data = []
            for field in fields:
                value = row.get(field, "-")
                formatted_value = format_value(value)
                row_data.append(sanitize_text(formatted_value))
            table_data.append(row_data)
        
        # Calcular largura das colunas dinamicamente
        page_width = pagesize[0] - 4*cm
        col_width = page_width / len(fields)
        
        # Criar tabela
        table = Table(table_data, colWidths=[col_width] * len(fields))
        
        # Estilo da tabela
        table_style = TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            
            # Corpo da tabela
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ])
        
        table.setStyle(table_style)
        elements.append(table)
        
        # Rodapé com informações
        elements.append(Spacer(1, 1*cm))
        footer_text = f"Total de registros: {len(data)}"
        footer = Paragraph(footer_text, subtitle_style)
        elements.append(footer)
    
    # Gerar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    """Endpoint principal para gerar PDF"""
    try:
        # Validar dados recebidos
        data = request.json
        
        required_fields = ['table_name', 'fields', 'supabase_url', 'anon_key']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo obrigatório ausente: {field}'}), 400
        
        table_name = data['table_name']
        fields = data['fields']
        supabase_url = data['supabase_url']
        anon_key = data['anon_key']
        
        # Validar campos
        if not isinstance(fields, list) or len(fields) == 0:
            return jsonify({'error': 'O campo "fields" deve ser uma lista não vazia'}), 400
        
        # Conectar ao Supabase
        try:
            supabase = create_client(supabase_url, anon_key)
        except Exception as e:
            return jsonify({'error': f'Erro ao conectar com Supabase: {str(e)}'}), 400
        
        # Buscar dados da tabela
        try:
            response = supabase.table(table_name).select(','.join(fields)).execute()
            table_data = response.data
        except Exception as e:
            return jsonify({'error': f'Erro ao buscar dados: {str(e)}'}), 400
        
        # Gerar PDF
        pdf_buffer = create_pdf(table_data, table_name, fields)
        
        # Retornar PDF
        filename = f"{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de verificação de saúde"""
    return jsonify({'status': 'ok', 'message': 'API funcionando corretamente'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)