import argparse
import sys

import yaml

from src.programacion import ProgramadorETL


def main():
    parser = argparse.ArgumentParser(description="Programador del pipeline ETL (schedule).")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--ahora", action="store_true", help="Ejecuta el pipeline al arrancar, además de la programación.")
    parser.add_argument("--una-vez", action="store_true", help="Ejecuta una sola vez y termina.")
    arguments = parser.parse_args()
    with open(arguments.config, encoding="utf-8") as file:
        config = yaml.safe_load(file)
    programador = ProgramadorETL(config)
    if arguments.una_vez:
        return 0 if programador.ejecutar_trabajo()["estado"] == "completada" else 1
    trabajo = programador.programar()
    print(f"Programador activo: {config['programacion']['frecuencia']} · próxima ejecución {trabajo.next_run:%Y-%m-%d %H:%M} · registro {programador.registro}")
    if arguments.ahora:
        programador.ejecutar_trabajo()
    try:
        programador.iniciar(espera_s=30)
    except KeyboardInterrupt:
        programador.detener()
        print("Programador detenido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
