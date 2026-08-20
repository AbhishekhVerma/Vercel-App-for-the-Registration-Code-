import os
import json
import re
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np

app = Flask(__name__)

# Path to the static catalog
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.xlsx')

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

def load_master_catalog(file_or_path):
    xl = pd.ExcelFile(file_or_path)
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
    return df_ct

@app.route('/api/catalog', methods=['GET'])
def get_catalog():
    try:
        xl = pd.ExcelFile(DATA_FILE)
        df_hum = pd.read_excel(xl, 'Humanities Option')
        hum_list = []
        for _, row in df_hum.iterrows():
            if pd.notna(row['Course']):
                hum_list.append({
                    'id': str(row['Course']).strip(),
                    'title': str(row['Description']).strip()
                })
        return jsonify({'humanities': hum_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        grid_data = json.loads(request.form.get('grid_data', '[]'))
        hum_mode = request.form.get('hum_mode', 'default')
        disc_mode = request.form.get('disc_mode', 'default')
        master_mode = request.form.get('master_mode', 'default')
        excluded_hum = json.loads(request.form.get('excluded_hum', '[]'))
        
        # Determine Master Catalog File
        master_data_source = DATA_FILE
        if master_mode == 'upload' and 'master_file' in request.files:
            master_data_source = request.files['master_file']
            
        df_ct = load_master_catalog(master_data_source)
        
        # 1. Parse Core Timetable from Grid Data
        core_occupied_slots = set()
        core_courses = set()
        base_timetable = []
        
        times = [
            "7:30-8:20", "8:25-9:15", "9:20-10:10", "10:15-11:05",
            "11:10-12:00", "12:05-12:55", "13:00-13:50", "13:55-14:45", "14:50-15:40"
        ]
        
        # Initialize empty base timetable
        for h in range(1, 10):
            base_timetable.append({'Hour': h, 'Time': times[h-1], 'Monday': '', 'Tuesday': '', 'Wednesday': '', 'Thursday': '', 'Friday': ''})
            
        for cell in grid_data:
            day = cell['day']
            hour = int(cell['hour'])
            course_id = str(cell['course']).strip()
            
            if course_id != '':
                core_occupied_slots.add((day, hour))
                core_courses.add(course_id)
                # find row in base_timetable
                for row in base_timetable:
                    if row['Hour'] == hour:
                        row[day] = course_id
        
        # Map core IDs to full names and find exams
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
                
        # Transform base_timetable IDs to names
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

        def process_list(eligible_courses):
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
                    'dh_parsed': dh,
                    'status': status,
                    'is_ok': status == "OK"
                })
            return results

        # Determine Disciplinary List
        disc_list = []
        if disc_mode in ['default', 'cs']:
            xl = pd.ExcelFile(master_data_source)
            try:
                df_disc = pd.read_excel(xl, 'Disciplinary Courses')
                disc_list = df_disc['Course'].dropna().str.strip().tolist()
            except Exception: pass
        elif disc_mode == 'biotech':
            disc_list = [
                'BIOT F242',
                'BIOT F345',
                'BIOT F347',
                'BIOT F413',
                'BIOT F416',
                'BIOT F420',
                'BIOT F492'
            ]
        elif disc_mode == 'upload' and 'disc_file' in request.files:
            try:
                df_disc = pd.read_excel(request.files['disc_file'])
                # Assuming standard format where column name includes 'Course'
                col = [c for c in df_disc.columns if 'Course' in str(c)]
                if col:
                    disc_list = df_disc[col[0]].dropna().str.strip().tolist()
                else:
                    disc_list = df_disc.iloc[:, 0].dropna().str.strip().tolist()
            except Exception: pass

        # Determine Humanities List
        hum_list = []
        if hum_mode == 'default':
            xl = pd.ExcelFile(master_data_source)
            df_hum = pd.read_excel(xl, 'Humanities Option')
            hum_list = df_hum['Course'].dropna().str.strip().tolist()
            # Filter out excluded humanities
            hum_list = [h for h in hum_list if h not in excluded_hum]
        elif hum_mode == 'upload' and 'hum_file' in request.files:
            try:
                df_hum = pd.read_excel(request.files['hum_file'])
                col = [c for c in df_hum.columns if 'Course' in str(c)]
                if col:
                    hum_list = df_hum[col[0]].dropna().str.strip().tolist()
                else:
                    hum_list = df_hum.iloc[:, 0].dropna().str.strip().tolist()
            except Exception: pass

        disc_matches = process_list(disc_list)
        hum_matches = process_list(hum_list)

        return jsonify({
            'base_timetable': base_timetable,
            'disciplinary': disc_matches,
            'humanities': hum_matches
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
