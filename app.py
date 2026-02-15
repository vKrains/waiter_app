print("ЗАГРУЖЕН app.py ИЗ:", __file__)
from fastapi.responses import FileResponse

from raspr import generate_svg_from_excel
from fastapi.responses import Response

import json
import sqlite3
from datetime import date as dt_date

import pandas as pd
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from engine import assign_shift, MAIN_POSITIONS, WEEKEND_ZONES

app = FastAPI()
templates = Jinja2Templates(directory="templates")

df = pd.read_excel("waiters.xlsx")
names = [str(x).strip() for x in df["name"].tolist() if str(x).strip()]
WAITERS = {i + 1: n for i, n in enumerate(names)}

EXCEL_FILE = "current_shift.xlsx"

conn = sqlite3.connect("history.db", check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS history (
    date TEXT NOT NULL,
    waiter_id INTEGER NOT NULL,
    zone TEXT NOT NULL,
    position INTEGER NULL
)
""")
conn.commit()


def load_history():
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT date, waiter_id, zone, position FROM history"
    ).fetchall()
    return [{"date": r[0], "waiter_id": r[1], "zone": r[2], "position": r[3]} for r in rows]

def generate_position_stats_excel():
    df_waiters = pd.read_excel("waiters.xlsx")
    names = [str(x).strip() for x in df_waiters["name"].tolist() if str(x).strip()]
    waiters_map = {i + 1: n for i, n in enumerate(names)}

    positions = list(range(1, 19))

    data = {}
    for wid, name in waiters_map.items():
        data[name] = {pos: 0 for pos in positions}
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT waiter_id, zone, position FROM history WHERE zone='Main' AND position IS NOT NULL"
    ).fetchall()

    for wid, zone, position in rows:
        if wid in waiters_map and position in positions:
            name = waiters_map[wid]
            data[name][position] += 1

    df_out = pd.DataFrame.from_dict(data, orient="index")
    df_out.index.name = "Фамилия"
    df_out = df_out.sort_index()

    output_path = "position_stats.xlsx"
    df_out.to_excel(output_path)

    return output_path


@app.get("/position-stats")
def download_position_stats():
    path = generate_position_stats_excel()
    return FileResponse(
        path,
        filename="position_stats.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )



@app.get("/plan", response_class=HTMLResponse)
def show_plan(request: Request):
    svg_content = generate_svg_from_excel(
        excel_path="current_shift.xlsx",
        polygons_path="polygons.json",
        svg_template_path="plan.svg",
    )

    return templates.TemplateResponse(
        "plan.html",
        {
            "request": request,
            "svg_content": svg_content,
        },
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "waiters": WAITERS,
            "result": None,
            "result_json": "",
            "selected_present": set(),
            "selected_shift_type": "weekday",
            "selected_date": dt_date.today().isoformat(),
            "selected_req_zone": {},
            "selected_req_pos": {},
            "error": None,
            "main_positions": MAIN_POSITIONS,
        },
    )

@app.post("/assign", response_class=HTMLResponse)
def assign(
    request: Request,
    shift_date: str = Form(...),
    shift_type: str = Form(...),
    present: list[str] = Form([]),
    req_wid: list[str] = Form([]),
    req_zone: list[str] = Form([]),
    req_pos: list[str] = Form([]),
):
    present_ids = [int(x) for x in present]

    requests_dict = {}

    for i in range(len(req_wid)):
        wid = int(req_wid[i])

        zone = req_zone[i] if i < len(req_zone) else "-"
        pos = req_pos[i] if i < len(req_pos) else "-"

        zone = zone.strip()
        pos = pos.strip()

        if zone in ("", "-"):
            continue

        if zone == "Main":
            if pos in ("", "-"):
                continue
            requests_dict[wid] = {
                "zone": "Main",
                "position": int(pos),
            }
        else:
            requests_dict[wid] = {
                "zone": zone,
                "position": None,
            }

    error = None
    result = None
    result_json = ""

    try:
        result = assign_shift(
            present=present_ids,
            requests=requests_dict,
            history=load_history(),
            shift_type=shift_type,
        )
        result_json = json.dumps(result, ensure_ascii=False)
    except Exception as e:
        error = str(e)

    selected_req_zone = {int(w): z for w, z in zip(req_wid, req_zone)}
    selected_req_pos = {int(w): p for w, p in zip(req_wid, req_pos)}

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "waiters": WAITERS,
            "result": result,
            "result_json": result_json,
            "selected_present": set(present_ids),
            "selected_shift_type": shift_type,
            "selected_date": shift_date,
            "selected_req_zone": selected_req_zone,
            "selected_req_pos": selected_req_pos,
            "error": error,
            "main_positions": MAIN_POSITIONS,
        },
    )
@app.post("/save", response_class=HTMLResponse)
def save(
    request: Request,
    shift_date: str = Form(...),
    shift_type: str = Form(...),
    result_json: str = Form(...),
):
    error = None
    result = None

    try:
        assignments = json.loads(result_json)

        # запись в историю
        for wid_str, a in assignments.items():
            conn.execute(
                "INSERT INTO history(date, waiter_id, zone, position) VALUES (?, ?, ?, ?)",
                (shift_date, int(wid_str), a["zone"], a["position"]),
            )
        conn.commit()

        # запись в Excel
        rows = []
        for wid_str, a in assignments.items():
            wid = int(wid_str)
            rows.append({
                "date": shift_date,
                "shift_type": shift_type,
                "waiter_id": wid,
                "waiter_name": WAITERS.get(wid, ""),
                "zone": a["zone"],
                "position": a["position"],
            })

        df_save = pd.DataFrame(rows)
        df_save.to_excel(EXCEL_FILE, index=False)

        result = assignments

    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "waiters": WAITERS,
            "result": result,
            "result_json": result_json,
            "selected_present": set(),
            "selected_shift_type": shift_type,
            "selected_date": shift_date,
            "selected_req_zone": {},
            "selected_req_pos": {},
            "error": error,
            "main_positions": MAIN_POSITIONS,
        },
    )

