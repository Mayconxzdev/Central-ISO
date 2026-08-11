from app.services.file_types import extension_category, normalize_extension


def test_normalize_extension_difficult_names():
    cases = {
        "arquivo.final.xlsx": ".xlsx",
        "arquivo.xlsx ": ".xlsx",
        "arquivo.": "nome terminado em ponto",
        ".gitignore": "sem extensao",
        "sem_extensao": "sem extensao",
        "arquivo.xlsx~": "temporario",
        "documento.backup.2024": "backup",
        "arquivo (2).PDF": ".pdf",
        "Medição_çãõ.xlsx": ".xlsx",
        "arquivo.docx[1]": "extensao invalida",
    }
    for filename, expected in cases.items():
        assert normalize_extension(filename) == expected


def test_extension_categories():
    assert extension_category(".pdf") == "pdf"
    assert extension_category(".docx") == "word"
    assert extension_category(".xlsm") == "excel"
    assert extension_category(".dwg") == "CAD/engenharia"
    assert extension_category("temporario") == "temporarios"
