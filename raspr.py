import pandas as pd
import json
import xml.etree.ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def svg_tag(tag):
    return f"{{{SVG_NS}}}{tag}"


def get_polygon_center(points):
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    return sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords)


def generate_svg_from_excel(
    excel_path="current_shift.xlsx",
    polygons_path="polygons.json",
    svg_template_path="plan.svg"
):

    df = pd.read_excel(excel_path)

    df = df[(df["zone"] == "Main") & (df["position"].notna())]

    df["Фамилия"] = df["waiter_name"].apply(lambda x: str(x).split()[0])

    position_map = {
        row["position"]: f"П{int(row['position'])} {row['Фамилия']}"
        for _, row in df.iterrows()
    }

    with open(polygons_path, "r", encoding="utf-8") as f:
        polygons = json.load(f)

    tree = ET.parse(svg_template_path)
    root = tree.getroot()

    for poly in polygons:
        pos_id = poly["id"]

        if pos_id not in position_map:
            continue

        cx, cy = get_polygon_center(poly["points"])

        text = ET.Element(svg_tag("text"), {
            "x": str(cx),
            "y": str(cy),
            "text-anchor": "middle",
            "dominant-baseline": "middle",
            "font-size": "14",
            "fill": "black"
        })

        text.text = position_map[pos_id]
        root.append(text)
        footer = ET.Element(svg_tag("text"), {
            "x": "20",
            "y": "98%",
            "font-size": "12",
            "fill": "#888888"
        })
        footer.text = "© 2026 VovaMark"
        root.append(footer)


    return ET.tostring(root, encoding="unicode")
