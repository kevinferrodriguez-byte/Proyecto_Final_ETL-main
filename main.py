import argparse
import sys

import yaml

from src.pipeline import Pipeline, STAGES

STAGE_HELP = (
    "bronce descarga las tres fuentes; plata reutiliza el último Bronce íntegro; indicadores reutiliza la última Plata aprobada; "
    "modelo reutiliza los últimos indicadores; escenarios reutiliza el último modelo; carga reutiliza el último modelo y escenarios."
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Pipeline ETL Medallion (Bronce, Plata y Oro) sobre riesgo demográfico y pensiones en España."
    )
    parser.add_argument("--desde", choices=STAGES, default=STAGES[0], help=f"Etapa inicial. {STAGE_HELP}")
    parser.add_argument("--hasta", choices=STAGES, default=STAGES[-1], help="Etapa final (incluida). Por defecto, carga.")
    parser.add_argument("--config", default="config/config.yaml", help="Ruta del archivo de configuración YAML.")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    try:
        with open(arguments.config, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        Pipeline(config).run(arguments.desde, arguments.hasta)
    except (OSError, ValueError, RuntimeError, KeyError, yaml.YAMLError) as error:
        print(f"El pipeline terminó con errores: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
