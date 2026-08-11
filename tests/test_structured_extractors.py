from datetime import date

from app.services.certificate_extractor import extract_from_filename, extract_from_csv_text, normalize_cert_number
from app.services.file_filters import is_noise_file, is_noise_path
from app.services.nc_extractor import extract_nc_from_path


def test_normalize_cert_number():
    assert normalize_cert_number("cpex demo-0001x") == "CPEx DEMO-0001X"


def test_extract_certificate_from_real_filename():
    extracted = extract_from_filename(
        "04 - PAINEL ELÉTRICO FABRICANTE DEMO A - CPEx DEMO-0001X Rev 00 - 06-02-2026.pdf",
        r"\\demo-server\quality-share\Clientes\CERTIFICADO\04 - PAINEL ELÉTRICO FABRICANTE DEMO A - CPEx DEMO-0001X Rev 00 - 06-02-2026.pdf",
    )
    assert extracted is not None
    assert extracted.number == "CPEx DEMO-0001X"
    assert extracted.valid_until == date(2026, 2, 6)
    assert "FABRICANTE DEMO A" in extracted.supplier.upper()


def test_extract_certificates_from_csv():
    text = "numero;fornecedor;componente;validade;situacao\nCPEx DEMO-0004X;FABRICANTE DEMO D;Plugues Ex;29/11/2027;vigente\n"
    rows = extract_from_csv_text("lista.csv", text)
    assert len(rows) == 1
    assert rows[0].number == "CPEx DEMO-0004X"
    assert rows[0].valid_until == date(2027, 11, 29)


def test_extract_nc_from_rq_tnc_folder():
    extracted = extract_nc_from_path(
        r"\\demo-server\quality-share\PQ-08 Melhoria\RQ-TNC_Não Conformidades\RQ-TNC 2025\RQ-TNC_003-2025_Gerencia\Evidencia\doc.pdf"
    )
    assert extracted is not None
    assert extracted.code == "NC 003/2025"
    assert extracted.area == "Gerência"


def test_noise_files_are_filtered():
    assert is_noise_path(r"\\demo-server\quality-share\@Recycle\CERTIFICADOS\file.pdf")
    assert is_noise_file("~$planilha.xlsx", r"\\demo-server\quality-share\PQ-02\~$planilha.xlsx", ".xlsx")
