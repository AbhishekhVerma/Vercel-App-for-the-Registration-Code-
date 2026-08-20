from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import re
import io

app = Flask(__name__)

def parse_dh(dh_str):
    if not isinstance(dh_str, str) or pd.isna(dh_str): return []
    matches = re.findall(r'(M|Th|T|W|F)(\d+)', dh_str)
    result = []
    day_map = {'M': 'Monday', 'T': 'Tuesday', 'W': 'Wednesday', 'Th': 'Thursday', 'F': 'Friday'}
    for day_abbr, hours in matches:
        day = day_map[day_abbr]
        for h in hours:
            result.append((day, int(h)))
    return result

def clean_exam(exam_str):
    if pd.isna(exam_str): return None
    s = str(exam_str).strip()
    if s in ['TBA', '-', '']: return None
    return s

@app.route('/', defaults={'path': ''}, methods=['POST'])
@app.route('/<path:path>', methods=['POST'])
def analyze(path):
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    try:
        xl = pd.ExcelFile(file)
    except Exception as e:
        return jsonify({'error': f'Failed to parse Excel file: {str(e)}'}), 400

    # 1. Parse Core Timetable
    df_tt = pd.read_excel(xl, 'Timetable')
    df_tt.columns = df_tt.columns.str.strip()
    
    core_occupied_slots = set()
    core_courses = set()
    base_timetable = []
    
    for idx, row in df_tt.iterrows():
        hour = int(row['Hour'])
        time_str = row['Time']
        row_data = {'Hour': hour, 'Time': time_str, 'Monday': '', 'Tuesday': '', 'Wednesday': '', 'Thursday': '', 'Friday': ''}
        
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            course = row[day]
            if pd.notna(course):
                course_str = str(course).strip()
                if course_str != '':
                    row_data[day] = course_str
                    core_occupied_slots.add((day, hour))
                    # Base course name matching
                    course_base = course_str[:-4] if course_str.endswith(" LAB") else course_str
                    core_courses.add(course_base)
        base_timetable.append(row_data)

    # 2. Parse Course Timetable
    df_ct = pd.read_excel(xl, 'Course Timetable', header=None)
    headers = ['CRSE_ID', 'COURSE NO.', 'S No', 'COURSE TITLE', 'L P U or CH', 'L or P', 'SEC', 'INSTRUCTOR', 'ROOM', 'DAYS/ HOURS', 'MIDSEM', 'COMPRE']
    df_ct.columns = headers
    df_ct = df_ct.iloc[3:].reset_index(drop=True)
    
    df_ct['is_new_course'] = df_ct['CRSE_ID'].notna() | (df_ct['COURSE NO.'].notna())
    df_ct['block_id'] = df_ct['is_new_course'].cumsum()
    
    df_ct['CRSE_ID'] = df_ct.groupby('block_id')['CRSE_ID'].ffill()
    df_ct['COURSE NO.'] = df_ct.groupby('block_id')['COURSE NO.'].ffill()
    df_ct['MIDSEM'] = df_ct.groupby('block_id')['MIDSEM'].ffill()
    df_ct['COMPRE'] = df_ct.groupby('block_id')['COMPRE'].ffill()
    df_ct['ACTUAL_COURSE_TITLE'] = df_ct.groupby('block_id')['COURSE TITLE'].transform(lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else np.nan)
    
    df_ct['CRSE_ID_STR'] = df_ct['CRSE_ID'].astype(str).str.replace(r'\.0$', '', regex=True)
    df_ct['COURSE_NO_STR'] = df_ct['COURSE NO.'].astype(str).str.strip()
    
    core_midsems = set()
    core_compres = set()
    id_to_name = {}
    
    for cc in core_courses:
        matched_rows = df_ct[
            (df_ct['COURSE_NO_STR'].str.fullmatch(cc, case=False)) |
            (df_ct['CRSE_ID_STR'].str.fullmatch(cc, case=False)) |
            (df_ct['ACTUAL_COURSE_TITLE'].str.contains(cc, case=False, na=False, regex=False))
        ]
        
        if not matched_rows.empty:
            actual_name = matched_rows.iloc[0]['ACTUAL_COURSE_TITLE']
            id_to_name[cc] = actual_name
            for _, r in matched_rows.iterrows():
                m = clean_exam(r['MIDSEM'])
                c = clean_exam(r['COMPRE'])
                if m: core_midsems.add(m)
                if c: core_compres.add(c)
        else:
            id_to_name[cc] = cc
            
    # Now, transform the base_timetable to replace IDs with their mapped full names
    for row in base_timetable:
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            val_str = row[day]
            if val_str != '':
                base_val = val_str[:-4] if val_str.endswith(" LAB") else val_str
                mapped_name = id_to_name.get(base_val, base_val)
                if val_str.endswith(" LAB") and not mapped_name.endswith("LAB"):
                    mapped_name += " LAB"
                row[day] = mapped_name
            
    def check_clash(row):
        clash_reasons = []
        dh = parse_dh(row['DAYS/ HOURS'])
        for d, h in dh:
            if (d, h) in core_occupied_slots:
                clash_reasons.append(f"Time clash at {d} {h}")
        m = clean_exam(row['MIDSEM'])
        c = clean_exam(row['COMPRE'])
        if m and m in core_midsems:
            clash_reasons.append(f"MIDSEM clash ({m})")
        if c and c in core_compres:
            clash_reasons.append(f"COMPRE clash ({c})")
        return list(set(clash_reasons)), dh

    def process_list(sheet_name):
        df_list = pd.read_excel(xl, sheet_name)
        eligible_courses = df_list['Course'].dropna().str.strip().tolist()
        
        matched_ct = df_ct[df_ct['COURSE NO.'].str.strip().isin(eligible_courses)].copy()
        
        results = []
        for _, r in matched_ct.iterrows():
            reasons, dh = check_clash(r)
            status = "; ".join(reasons) if reasons else "OK"
            
            c_title = r['ACTUAL_COURSE_TITLE']
            if pd.isna(c_title): c_title = str(r['COURSE NO.'])
            if pd.notna(r['L or P']): c_title += f" ({r['L or P']})"
                
            results.append({
                's_no': float(r['S No']) if pd.notna(r['S No']) else None,
                'crse_id': float(r['CRSE_ID']) if pd.notna(r['CRSE_ID']) else None,
                'course_no': str(r['COURSE NO.']),
                'title': str(c_title),
                'l_or_p': str(r['L or P']) if pd.notna(r['L or P']) else '',
                'dh_string': str(r['DAYS/ HOURS']) if pd.notna(r['DAYS/ HOURS']) else '',
                'dh_parsed': dh, # e.g. [["Monday", 4], ...]
                'status': status,
                'is_ok': status == "OK"
            })
        return results

    disc_matches = process_list('Disciplinary Courses')
    hum_matches = process_list('Humanities Option')
    
    return jsonify({
        'base_timetable': base_timetable,
        'disciplinary': disc_matches,
        'humanities': hum_matches
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
