import glob
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import tempus

_DO_Commune = "Commune"
_DO_Ordo = "Ordo"
_DO_Sancti = "Sancti"
_DO_Tempora = "Tempora"


def get_date_to_liturgical_calendar(date: datetime) -> str:
    return f"{date.month:02}-{date.day:02}"


def get_divinum_officium_files_path() -> str:
    current_dir_abspath = Path(__file__).resolve().parent
    files_location = Path(
        current_dir_abspath, "..", "divinum-officium", "web", "www", "missa"
    ).resolve()

    return str(files_location)


def get_date_to_tempora(now: datetime) -> Optional[str]:
    converted = tempus.get_tempora_for_advent(now)

    if converted is not None:
        return converted

    converted = tempus.get_tempora_for_epiphany(now)
    if converted is not None:
        return converted

    converted = tempus.get_tempora_for_quadp(now)
    if converted is not None:
        return converted

    converted = tempus.get_tempora_for_lent(now)
    if converted is not None:
        return converted

    converted = tempus.get_tempora_for_pasch(now)
    if converted is not None:
        return converted

    converted = tempus.get_tempora_for_pentecost(now)
    if converted is not None:
        return converted

    return None


def language_code_to_name(code: str) -> str:
    match code.lower():
        case "la":
            return "Latin"
        case "da":
            return "Dansk"
        case "de":
            return "Deutsch"
        case "en":
            return "English"
        case "es":
            return "Espanol"
        case "fr":
            return "Francais"
        case "it":
            return "Italiano"
        case "hu":
            return "Magyar"
        case "nl":
            return "Nederlands"
        case "pl":
            return "Polski"
        case "pt":
            return "Portugues"
        case "uk":
            return "Ukrainian"
        case _:
            raise ValueError(f"{code} not found")


def get_propers_for_date(date: datetime, lang="") -> Dict[str, List[str]]:
    do_path = get_divinum_officium_files_path()
    litcal = get_date_to_liturgical_calendar(date) + "*"
    tempora = get_date_to_tempora(date)
    if tempora is None:
        tempora = ""
    else:
        tempora = tempora + "*"

    name_latin = language_code_to_name("la")

    sancti_files = glob.glob(litcal, root_dir=Path(do_path, name_latin, _DO_Sancti))
    tempora_files = glob.glob(tempora, root_dir=Path(do_path, name_latin, _DO_Tempora))
    files = {"sancti": sancti_files, "tempora": tempora_files}

    if lang == "":
        return files

    name_other_lang = language_code_to_name(lang)

    files["sancti_other"] = glob.glob(
        litcal, root_dir=Path(do_path, name_other_lang, _DO_Sancti)
    )
    files["tempora_other"] = glob.glob(
        tempora, root_dir=Path(do_path, name_other_lang, _DO_Tempora)
    )

    return files
