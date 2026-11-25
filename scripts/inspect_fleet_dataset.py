import zipfile
import xml.etree.ElementTree as ET
import os
import json

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "..", "datasets", "LoadLink_Demo_Fleet_Dataset.xlsx")

def parse_xlsx(file_path):
    wb = zipfile.ZipFile(file_path)
    
    # Read shared strings if any
    shared_strings = []
    if 'xl/sharedStrings.xml' in wb.namelist():
        s_xml = ET.fromstring(wb.read('xl/sharedStrings.xml'))
        for si in s_xml.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
            texts = [t.text or '' for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')]
            shared_strings.append(''.join(texts))

    wb_rels = ET.fromstring(wb.read('xl/_rels/workbook.xml.rels'))
    rel_map = {}
    for r in wb_rels.findall('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
        rel_map[r.attrib['Id']] = r.attrib['Target'].lstrip('/')

    wb_xml = ET.fromstring(wb.read('xl/workbook.xml'))
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    
    result = {}
    
    for s in wb_xml.findall('m:sheets/m:sheet', ns):
        name = s.attrib['name']
        rid = s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        target = rel_map[rid]
        if not target.startswith('xl/'):
            target = 'xl/' + target
        
        sheet_xml = ET.fromstring(wb.read(target))
        rows = sheet_xml.findall('m:sheetData/m:row', ns)
        
        parsed_rows = []
        for r in rows:
            row_idx = int(r.attrib.get('r', 0))
            cells = {}
            for c in r.findall('m:c', ns):
                coord = c.attrib.get('r', '')
                col_letters = ''.join([ch for ch in coord if ch.isalpha()])
                t = c.attrib.get('t')
                
                # Extract value
                val = None
                if t == 's':
                    v_elem = c.find('m:v', ns)
                    if v_elem is not None and v_elem.text:
                        val = shared_strings[int(v_elem.text)]
                elif t == 'b':
                    v_elem = c.find('m:v', ns)
                    val = (v_elem.text == '1') if v_elem is not None else False
                elif t == 'inlineStr':
                    texts = list(c.itertext())
                    val = ''.join(texts)
                else:
                    v_elem = c.find('m:v', ns)
                    if v_elem is not None:
                        val = v_elem.text
                    else:
                        texts = list(c.itertext())
                        val = ''.join(texts) if texts else None
                cells[col_letters] = val
            parsed_rows.append(cells)
            
        result[name] = parsed_rows
    return result

if __name__ == "__main__":
    data = parse_xlsx(EXCEL_PATH)
    for sheet_name, rows in data.items():
        print(f"\n========================================================")
        print(f"SHEET: {sheet_name} (Total rows: {len(rows)})")
        print(f"========================================================")
        if not rows:
            print("Empty sheet.")
            continue
        header_row = rows[0]
        # Sort cols by letter order (A, B, C...)
        sorted_cols = sorted(header_row.keys(), key=lambda x: (len(x), x))
        headers = [f"{col}: {header_row[col]}" for col in sorted_cols]
        print("Columns:")
        for h in headers:
            print(f"  {h}")
        if len(rows) > 1:
            print("\nSample Row 1:")
            for col in sorted_cols:
                print(f"  {col} ({header_row.get(col)}): {rows[1].get(col)}")
        if len(rows) > 2:
            print("\nSample Row 2:")
            for col in sorted_cols:
                print(f"  {col} ({header_row.get(col)}): {rows[2].get(col)}")
