from pathlib import Path

aqui = Path(__file__).parent
datos = (aqui / "datos.json").read_text(encoding="utf-8").replace("</", "<\\/")
html = (aqui / "plantilla.html").read_text(encoding="utf-8").replace("__DATOS__", datos)
salida = aqui / "pensiones_espana.html"
# Documento completo: se abre directamente en el navegador o se sube a cualquier hosting estático
cabecera = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            "<style>body{margin:0}[hidden]{display:none!important}</style>\n</head>\n<body>\n")
salida.write_text(cabecera + html + "\n</body>\n</html>\n", encoding="utf-8")
print(salida, round(salida.stat().st_size / 1024), "KB")
