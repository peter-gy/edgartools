from pathlib import Path

import pytest
from rich import print

from edgar import Filing
from edgar.xbrl.parser import (parse_label_linkbase, parse_calculation_linkbase, parse_definition_linkbase, XBRLData, XbrlDocuments,
                               XBRLInstance, XBRLPresentation, StatementDefinition, StatementData)

# Sample XML strings for testing
SAMPLE_INSTANCE_XML = """
<xbrl xml:lang="en-US"
      xmlns="http://www.xbrl.org/2003/instance"
      xmlns:dei="http://xbrl.sec.gov/dei/2023"
      xmlns:us-gaap="http://fasb.org/us-gaap/2023">
    <context id="ctx1">
        <entity><identifier>1234567890</identifier></entity>
        <period>
            <startDate>2023-01-01</startDate>
            <endDate>2023-12-31</endDate>
        </period>
    </context>
    <us-gaap:Assets contextRef="ctx1" unitRef="usd" decimals="-6">1000000</us-gaap:Assets>
    <us-gaap:Liabilities contextRef="ctx1" unitRef="usd" decimals="-6">500000</us-gaap:Liabilities>
    <dei:DocumentPeriodEndDate contextRef="ctx1">2023-12-31</dei:DocumentPeriodEndDate>
</xbrl>
"""

SAMPLE_PRESENTATION_XML = """
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:schemaLocation="http://www.xbrl.org/2003/linkbase http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd">
<link:roleRef roleURI="http://www.company.com/role/CONSOLIDATEDBALANCESHEETS" xlink:type="simple" xlink:href="aapl-20230930.xsd#CoverPage"/>
<link:presentationLink xlink:role="http://www.company.com/role/CONSOLIDATEDBALANCESHEETS">
    <link:loc xlink:label="loc_assets" xlink:href="#us-gaap_Assets"/>
    <link:loc xlink:label="loc_liabilities" xlink:href="#us-gaap_Liabilities"/>
    <link:presentationArc xlink:from="assets" xlink:to="liabilities" order="1"/>
</link:presentationLink>
</link:linkbase>
"""


@pytest.fixture
def sample_instance():
    return XBRLInstance.parse(SAMPLE_INSTANCE_XML)


@pytest.fixture
def sample_presentation():
    return XBRLPresentation.parse(SAMPLE_PRESENTATION_XML)


@pytest.fixture
def sample_labels():
    return {
        'us-gaap_Assets': {'label': 'Assets'},
        'us-gaap_Liabilities': {'label': 'Liabilities'}
    }


@pytest.fixture
def sample_calculations():
    return {}


def test_xbrl_instance_parsing(sample_instance):
    assert len(sample_instance.facts) == 3
    assert sample_instance.get_document_period() == '2023-12-31'


def test_xbrl_instance_query_facts(sample_instance):
    assets = sample_instance.query_facts(concept='us-gaap:Assets')
    assert len(assets) == 1
    assert assets.iloc[0]['value'] == '1000000'


def test_xbrl_presentation_parsing(sample_presentation):
    assert len(sample_presentation.roles) == 1
    role = "http://www.company.com/role/CONSOLIDATEDBALANCESHEETS"
    assert role in sample_presentation.roles
    assert len(sample_presentation.roles[role].children) == 2


def test_financial_statement_creation(sample_instance, sample_presentation, sample_labels, sample_calculations):
    role = "http://www.company.com/role/CONSOLIDATEDBALANCESHEETS"
    statement = StatementDefinition.create(
        "Balance Sheet",
        sample_presentation.roles[role],
        sample_labels,
        sample_calculations,
        sample_instance
    )
    assert statement.name == "Balance Sheet"
    assert len(statement.line_items) == 2


def test_xbrl_parser_get_financial_statement(sample_instance, sample_presentation, sample_labels, sample_calculations):
    parser = XBRLData(
        instance=sample_instance,
        presentation=sample_presentation,
        labels=sample_labels,
        calculations=sample_calculations
    )
    parser.parse_financial_statements()

    statement: StatementData = parser.get_statement("CONSOLIDATEDBALANCESHEETS")
    assert statement is not None
    assert 'Assets' in statement.labels
    assert 'Liabilities' in statement.labels
    assert '2023' in statement.periods


@pytest.mark.asyncio
async def test_xbrl_parser_from_filing():
    filing = Filing(company='Accenture plc', cik=1467373, form='10-K', filing_date='2023-10-12',
                    accession_no='0001467373-23-000324')

    parser = await XBRLData.from_filing(filing)
    assert isinstance(parser, XBRLData)
    assert isinstance(parser.instance, XBRLInstance)
    assert isinstance(parser.presentation, XBRLPresentation)


def test_parse_xbrl_presentation():
    presentation = XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())
    _repr_ = repr(presentation)
    print(_repr_)
    assert "EntitiesTable" in _repr_
    assert "A1.375NotesDue2024Member" in _repr_


def test_xbrl_presentation_get_structure_for_role():
    presentation = XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())
    structure = presentation.get_structure('http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS')
    assert structure
    print(structure)


def test_xbrl_presentation_list_roles():
    presentation = XBRLPresentation.parse(Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text())
    roles = presentation.list_roles()
    assert 'http://www.apple.com/role/Leases' in roles


def test_parse_labels():
    labels = parse_label_linkbase(Path('data/xbrl/datafiles/aapl/aapl-20230930_lab.xml').read_text())
    assert labels['us-gaap_ResearchAndDevelopmentExpense']['label'] == 'Research and Development Expense'


def test_parse_calculations():
    calculations = parse_calculation_linkbase(Path('data/xbrl/datafiles/aapl/aapl-20230930_cal.xml').read_text())
    assert calculations
    assert calculations['http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS']


def test_parse_definitions():
    definitions = parse_definition_linkbase(Path('data/xbrl/datafiles/aapl/aapl-20230930_def.xml').read_text())
    assert definitions


@pytest.mark.asyncio
async def test_parse_xbrl_document_for_filing_with_embedded_linkbase():
    filing = Filing(company='HUBSPOT INC', cik=1404655, form='10-K', filing_date='2024-02-14',
                    accession_no='0000950170-24-015277')
    xbrl_documents = XbrlDocuments(filing.attachments)
    instance_xml, presentation_xml, labels, calculations = await xbrl_documents.load()
    assert presentation_xml
    assert labels
    assert calculations
    assert instance_xml

    xbrl_data: XBRLData = await XBRLData.from_filing(filing)
    assert xbrl_data
    assert len(xbrl_data.statements) == 98


def test_financial_filing_with_no_attachments():
    filing = Filing(form='10-Q', filing_date='2024-07-15', company='Legacy Education Alliance, Inc.', cik=1561880,
                    accession_no='0001493152-24-027895')
    xbrl_data = XBRLData.extract(filing)
    assert xbrl_data is None


def test_filing_with_no_namespace_labels():
    filing = Filing(form='10-K/A', filing_date='2024-07-25', company='RITE AID CORP',
                    cik=84129, accession_no='0001558370-24-010167')
    xbrl_documents: XbrlDocuments = XbrlDocuments(filing.attachments)
    assert xbrl_documents.get('label') is not None
    print(xbrl_documents)
    xbrl_data:XBRLData = XBRLData.extract(filing)
    print(xbrl_data.labels)

