from app.services.telegram_offer_parser import TelegramOfferParser


def test_parse_amazon_offer_extracts_expected_fields() -> None:
    parser = TelegramOfferParser(business_timezone="America/Manaus")
    message = {
        "id": 883696,
        "date_iso": "2026-03-25T22:02:51+00:00",
        "text": (
            "Processador AMD Ryzen 7 9800X3D, 8-Core, SMT, AM5, PCIe x16 5.0 "
            "R$ 2.799,99 em 10 parcelas Frete Grátis (consulte o CEP) Avaliação:  "
            "Loja: Amazon https://www.pcbuildwizard.com/product/N1nnkp/amazon.com.br?source=pcbuildwizard-tg "
            "Menor preço em 90 dias: R$ 2.679,98 Mediana dos preços de 90 dias: R$ 2.980,35"
        ),
        "url": "https://t.me/pcbuildwizard/883696",
    }

    offer = parser.parse(
        message,
        entity_type="cpu",
        entity_sku="100-100001084WOF",
        entity_name="AMD Ryzen 7 9800X3D",
    )

    assert offer.business_date == "2026-03-25"
    assert offer.entity_type == "cpu"
    assert offer.entity_sku == "100-100001084WOF"
    assert offer.store == "amazon"
    assert offer.store_display_name == "Amazon"
    assert offer.price_card == 2799.99
    assert offer.installments == 10
    assert offer.source_url == "https://www.pcbuildwizard.com/product/N1nnkp/amazon.com.br?source=pcbuildwizard-tg"
    assert offer.telegram_message_id == 883696
    assert offer.telegram_message_url == "https://t.me/pcbuildwizard/883696"
    assert offer.posted_at == "2026-03-25T22:02:51Z"
    assert offer.lowest_price_90d == 2679.98
    assert offer.median_price_90d == 2980.35


def test_parse_kabum_offer_uses_business_timezone_for_date() -> None:
    parser = TelegramOfferParser(business_timezone="America/Manaus")
    message = {
        "id": 882613,
        "date_iso": "2026-03-26T01:30:00+00:00",
        "text": (
            "Processador AMD Ryzen 7 9800X3D, 8-Core, SMT, AM5, PCIe x16 5.0 "
            "R$ 2.800,00 em 10 parcelas Avaliação:   Loja: KaBuM! "
            "https://www.awin1.com/cread.php?awinmid=17729&awinaffid=1139853&ued=https%3A%2F%2Fwww.kabum.com.br%2Fproduto%2F662405%2F&clickref=pcbuildwizard-tg "
            "Menor preço em 90 dias: R$ 2.679,98 Mediana dos preços de 90 dias: R$ 2.985,90"
        ),
        "url": "https://t.me/pcbuildwizard/882613",
    }

    offer = parser.parse(
        message,
        entity_type="cpu",
        entity_sku="100-100001084WOF",
        entity_name="AMD Ryzen 7 9800X3D",
    )

    assert offer.business_date == "2026-03-25"
    assert offer.store == "kabum"
    assert offer.store_display_name == "KaBuM!"
    assert offer.price_card == 2800.0
    assert offer.lowest_price_90d == 2679.98
    assert offer.median_price_90d == 2985.90


def test_parse_raises_when_store_is_missing() -> None:
    parser = TelegramOfferParser()
    message = {
        "id": 10,
        "date_iso": "2026-03-25T22:02:51+00:00",
        "text": "Processador AMD Ryzen 7 9800X3D R$ 2.799,99",
    }

    try:
        parser.parse(message, entity_type="cpu", entity_sku="sku", entity_name="cpu")
    except ValueError as exc:
        assert str(exc) == "Could not extract store from Telegram message."
    else:
        raise AssertionError("Expected parser to reject messages without store.")


def test_parse_infers_store_from_url_when_label_is_missing() -> None:
    parser = TelegramOfferParser()
    message = {
        "id": 882613,
        "date_iso": "2026-03-25T22:02:51+00:00",
        "text": (
            "Processador AMD Ryzen 7 9800X3D R$ 2.800,00 em 10 parcelas "
            "https://www.awin1.com/cread.php?awinmid=17729&awinaffid=1139853&ued=https%3A%2F%2Fwww.kabum.com.br%2Fproduto%2F662405%2F&clickref=pcbuildwizard-tg"
        ),
        "url": "https://t.me/pcbuildwizard/882613",
    }

    offer = parser.parse(
        message,
        entity_type="cpu",
        entity_sku="100-100001084WOF",
        entity_name="AMD Ryzen 7 9800X3D",
    )

    assert offer.store == "kabum"
    assert offer.store_display_name == "kabum"
    assert offer.source_url is not None
