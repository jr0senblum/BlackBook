"""Exhaustive tests for PrefixParserService.

Pure-computation tests — no database, no async, no fixtures needed.
See REQUIREMENTS.md §9.6 and PHASE2.md Unit 1 for the full spec.
"""

import pytest

from app.services.prefix_parser_service import ParsedLine, ParsedSource, parse


# ── Routing keys → stored in fields, NOT in lines ────────────────


class TestRoutingKeys:
    """nc:, c:, cid: are extracted into ParsedSource fields."""

    def test_nc_extracted(self) -> None:
        result = parse("nc: Acme Corp")
        assert result.nc == "Acme Corp"
        assert result.lines == []

    def test_c_extracted(self) -> None:
        result = parse("c: Existing Corp")
        assert result.c == "Existing Corp"
        assert result.lines == []

    def test_cid_extracted(self) -> None:
        result = parse("cid: 550e8400-e29b-41d4-a716-446655440000")
        assert result.cid == "550e8400-e29b-41d4-a716-446655440000"
        assert result.lines == []

    def test_multiple_routing_all_stored(self) -> None:
        """PrefixParserService stores all routing fields — validation is
        IngestionService's job (§9.7)."""
        result = parse("nc: New Corp\nc: Old Corp\ncid: some-id")
        assert result.nc == "New Corp"
        assert result.c == "Old Corp"
        assert result.cid == "some-id"
        assert result.lines == []


# ── Metadata keys → stored in fields, NOT in lines ──────────────


class TestMetadataKeys:
    """who:, date:, src: are extracted into ParsedSource fields."""

    def test_who_extracted(self) -> None:
        result = parse("who: Jane Smith")
        assert result.who == "Jane Smith"
        assert result.lines == []

    def test_date_extracted(self) -> None:
        result = parse("date: 2025-03-15")
        assert result.date == "2025-03-15"
        assert result.lines == []

    def test_src_extracted(self) -> None:
        result = parse("src: Q4 interview")
        assert result.src == "Q4 interview"
        assert result.lines == []

    def test_contact_alias_resolves_to_who(self) -> None:
        result = parse("contact: Bob Jones")
        assert result.who == "Bob Jones"
        assert result.lines == []

    def test_from_alias_resolves_to_who(self) -> None:
        result = parse("from: Alice Green")
        assert result.who == "Alice Green"
        assert result.lines == []

    def test_d_alias_resolves_to_date(self) -> None:
        result = parse("d: March 15")
        assert result.date == "March 15"
        assert result.lines == []

    def test_when_alias_resolves_to_date(self) -> None:
        result = parse("when: last Tuesday")
        assert result.date == "last Tuesday"
        assert result.lines == []

    def test_source_alias_resolves_to_src(self) -> None:
        result = parse("source: board deck")
        assert result.src == "board deck"
        assert result.lines == []

    def test_via_alias_resolves_to_src(self) -> None:
        result = parse("via: email thread")
        assert result.src == "email thread"
        assert result.lines == []


# ── Content keys → emitted into lines ────────────────────────────


class TestContentKeys:
    """All non-routing, non-metadata canonical keys emit into lines."""

    def test_person_key(self) -> None:
        result = parse("p: Jane Smith, VP Engineering")
        assert result.lines == [
            ParsedLine(canonical_key="p", text="Jane Smith, VP Engineering")
        ]

    def test_person_alias(self) -> None:
        result = parse("person: John Doe")
        assert result.lines == [ParsedLine(canonical_key="p", text="John Doe")]

    def test_pe_alias(self) -> None:
        result = parse("pe: Alice Green")
        assert result.lines == [ParsedLine(canonical_key="p", text="Alice Green")]

    def test_functional_area_key(self) -> None:
        result = parse("fn: Engineering")
        assert result.lines == [ParsedLine(canonical_key="fn", text="Engineering")]

    def test_func_alias(self) -> None:
        result = parse("func: Product")
        assert result.lines == [ParsedLine(canonical_key="fn", text="Product")]

    def test_area_alias(self) -> None:
        result = parse("area: Sales")
        assert result.lines == [ParsedLine(canonical_key="fn", text="Sales")]

    def test_team_alias(self) -> None:
        result = parse("team: Marketing")
        assert result.lines == [ParsedLine(canonical_key="fn", text="Marketing")]

    def test_technology_key(self) -> None:
        result = parse("t: Kubernetes")
        assert result.lines == [ParsedLine(canonical_key="t", text="Kubernetes")]

    def test_tech_alias(self) -> None:
        result = parse("tech: Terraform")
        assert result.lines == [ParsedLine(canonical_key="t", text="Terraform")]

    def test_stack_alias(self) -> None:
        result = parse("stack: PostgreSQL")
        assert result.lines == [ParsedLine(canonical_key="t", text="PostgreSQL")]

    def test_process_key(self) -> None:
        result = parse("proc: CI/CD pipeline")
        assert result.lines == [
            ParsedLine(canonical_key="proc", text="CI/CD pipeline")
        ]

    def test_process_alias(self) -> None:
        result = parse("process: Agile sprints")
        assert result.lines == [
            ParsedLine(canonical_key="proc", text="Agile sprints")
        ]

    def test_how_alias(self) -> None:
        result = parse("how: daily standups")
        assert result.lines == [
            ParsedLine(canonical_key="proc", text="daily standups")
        ]

    def test_note_key(self) -> None:
        result = parse("n: some plain note")
        assert result.lines == [ParsedLine(canonical_key="n", text="some plain note")]

    def test_note_alias(self) -> None:
        result = parse("note: another note")
        assert result.lines == [ParsedLine(canonical_key="n", text="another note")]


# ── CGKRA keys ───────────────────────────────────────────────────


class TestCGKRAKeys:
    """CGKRA canonical keys and aliases."""

    def test_cs_key(self) -> None:
        result = parse("cs: company is growing rapidly")
        assert result.lines == [
            ParsedLine(canonical_key="cs", text="company is growing rapidly")
        ]

    def test_cur_alias(self) -> None:
        result = parse("cur: 500 employees")
        assert result.lines == [ParsedLine(canonical_key="cs", text="500 employees")]

    def test_current_alias(self) -> None:
        result = parse("current: Series B funded")
        assert result.lines == [
            ParsedLine(canonical_key="cs", text="Series B funded")
        ]

    def test_gw_key(self) -> None:
        result = parse("gw: strong engineering culture")
        assert result.lines == [
            ParsedLine(canonical_key="gw", text="strong engineering culture")
        ]

    def test_well_alias(self) -> None:
        result = parse("well: retention is high")
        assert result.lines == [
            ParsedLine(canonical_key="gw", text="retention is high")
        ]

    def test_kp_key(self) -> None:
        result = parse("kp: tech debt in payments service")
        assert result.lines == [
            ParsedLine(canonical_key="kp", text="tech debt in payments service")
        ]

    def test_prob_alias(self) -> None:
        result = parse("prob: slow release cycle")
        assert result.lines == [
            ParsedLine(canonical_key="kp", text="slow release cycle")
        ]

    def test_problem_alias(self) -> None:
        result = parse("problem: no monitoring")
        assert result.lines == [
            ParsedLine(canonical_key="kp", text="no monitoring")
        ]

    def test_rm_key(self) -> None:
        result = parse("rm: migrate to cloud native")
        assert result.lines == [
            ParsedLine(canonical_key="rm", text="migrate to cloud native")
        ]

    def test_road_alias(self) -> None:
        result = parse("road: launch mobile app Q3")
        assert result.lines == [
            ParsedLine(canonical_key="rm", text="launch mobile app Q3")
        ]

    def test_roadmap_alias(self) -> None:
        result = parse("roadmap: expand to EU market")
        assert result.lines == [
            ParsedLine(canonical_key="rm", text="expand to EU market")
        ]

    def test_aop_key(self) -> None:
        result = parse("aop: AI-driven analytics opportunity")
        assert result.lines == [
            ParsedLine(canonical_key="aop", text="AI-driven analytics opportunity")
        ]


# ── SWOT keys ────────────────────────────────────────────────────


class TestSWOTKeys:
    """SWOT canonical keys and aliases."""

    def test_s_key(self) -> None:
        result = parse("s: strong brand recognition")
        assert result.lines == [
            ParsedLine(canonical_key="s", text="strong brand recognition")
        ]

    def test_str_alias(self) -> None:
        result = parse("str: experienced leadership team")
        assert result.lines == [
            ParsedLine(canonical_key="s", text="experienced leadership team")
        ]

    def test_strength_alias(self) -> None:
        result = parse("strength: market leader in segment")
        assert result.lines == [
            ParsedLine(canonical_key="s", text="market leader in segment")
        ]

    def test_plus_alias(self) -> None:
        result = parse("+: great customer satisfaction")
        assert result.lines == [
            ParsedLine(canonical_key="s", text="great customer satisfaction")
        ]

    def test_w_key(self) -> None:
        result = parse("w: limited international presence")
        assert result.lines == [
            ParsedLine(canonical_key="w", text="limited international presence")
        ]

    def test_weak_alias(self) -> None:
        result = parse("weak: aging infrastructure")
        assert result.lines == [
            ParsedLine(canonical_key="w", text="aging infrastructure")
        ]

    def test_weakness_alias(self) -> None:
        result = parse("weakness: high attrition in sales")
        assert result.lines == [
            ParsedLine(canonical_key="w", text="high attrition in sales")
        ]

    def test_minus_alias(self) -> None:
        result = parse("-: poor documentation practices")
        assert result.lines == [
            ParsedLine(canonical_key="w", text="poor documentation practices")
        ]

    def test_o_key(self) -> None:
        result = parse("o: emerging market in Asia")
        assert result.lines == [
            ParsedLine(canonical_key="o", text="emerging market in Asia")
        ]

    def test_opp_alias(self) -> None:
        result = parse("opp: partnership with FinCo")
        assert result.lines == [
            ParsedLine(canonical_key="o", text="partnership with FinCo")
        ]

    def test_opportunity_alias(self) -> None:
        result = parse("opportunity: regulatory tailwinds")
        assert result.lines == [
            ParsedLine(canonical_key="o", text="regulatory tailwinds")
        ]

    def test_th_key(self) -> None:
        result = parse("th: new competitor entering market")
        assert result.lines == [
            ParsedLine(canonical_key="th", text="new competitor entering market")
        ]

    def test_threat_alias(self) -> None:
        result = parse("threat: tariff increases")
        assert result.lines == [
            ParsedLine(canonical_key="th", text="tariff increases")
        ]

    def test_risk_alias(self) -> None:
        result = parse("risk: supply chain disruption")
        assert result.lines == [
            ParsedLine(canonical_key="th", text="supply chain disruption")
        ]


# ── Action item keys ─────────────────────────────────────────────


class TestActionItemKeys:
    """Action item canonical key and aliases."""

    def test_a_key(self) -> None:
        result = parse("a: schedule follow-up interview")
        assert result.lines == [
            ParsedLine(canonical_key="a", text="schedule follow-up interview")
        ]

    def test_action_alias(self) -> None:
        result = parse("action: draft proposal by Friday")
        assert result.lines == [
            ParsedLine(canonical_key="a", text="draft proposal by Friday")
        ]

    def test_todo_alias(self) -> None:
        result = parse("todo: review org chart")
        assert result.lines == [
            ParsedLine(canonical_key="a", text="review org chart")
        ]

    def test_do_alias(self) -> None:
        result = parse("do: send report to team")
        assert result.lines == [
            ParsedLine(canonical_key="a", text="send report to team")
        ]


# ── Relationship lines ──────────────────────────────────────────


class TestRelationshipLines:
    """rel: lines require > separator validation."""

    def test_well_formed_rel(self) -> None:
        result = parse("rel: Jane Smith > Bob Jones")
        assert result.lines == [
            ParsedLine(canonical_key="rel", text="Jane Smith > Bob Jones")
        ]

    def test_rel_with_reports_alias(self) -> None:
        result = parse("reports: Alice > Charlie")
        assert result.lines == [
            ParsedLine(canonical_key="rel", text="Alice > Charlie")
        ]

    def test_rel_with_under_alias(self) -> None:
        result = parse("under: Dave > Eve")
        assert result.lines == [
            ParsedLine(canonical_key="rel", text="Dave > Eve")
        ]

    def test_malformed_rel_no_separator(self) -> None:
        """rel: without > is emitted as n: with the full original line."""
        result = parse("rel: Jane Smith reports to Bob Jones")
        assert result.lines == [
            ParsedLine(
                canonical_key="n",
                text="rel: Jane Smith reports to Bob Jones",
            )
        ]

    def test_malformed_rel_alias_no_separator(self) -> None:
        """reports: without > is also emitted as n: with full line."""
        result = parse("reports: Alice under Charlie")
        assert result.lines == [
            ParsedLine(
                canonical_key="n",
                text="reports: Alice under Charlie",
            )
        ]


# ── Unrecognized prefixes ───────────────────────────────────────


class TestUnrecognizedPrefixes:
    """Unrecognized prefixes are treated as n: with full line."""

    def test_unrecognized_prefix(self) -> None:
        result = parse("xyz: some random text")
        assert result.lines == [
            ParsedLine(canonical_key="n", text="xyz: some random text")
        ]

    def test_another_unrecognized(self) -> None:
        result = parse("foobar: hello world")
        assert result.lines == [
            ParsedLine(canonical_key="n", text="foobar: hello world")
        ]


# ── Lines without prefix ────────────────────────────────────────


class TestLinesWithoutPrefix:
    """Lines without any colon are treated as n: with full line."""

    def test_no_colon_line(self) -> None:
        result = parse("This is a plain text line without any prefix")
        assert result.lines == [
            ParsedLine(
                canonical_key="n",
                text="This is a plain text line without any prefix",
            )
        ]

    def test_just_text(self) -> None:
        result = parse("just some text")
        assert result.lines == [
            ParsedLine(canonical_key="n", text="just some text")
        ]


# ── Blank lines ──────────────────────────────────────────────────


class TestBlankLines:
    """Blank lines are discarded."""

    def test_blank_lines_discarded(self) -> None:
        result = parse("p: Alice\n\n\np: Bob")
        assert len(result.lines) == 2
        assert result.lines[0].text == "Alice"
        assert result.lines[1].text == "Bob"

    def test_only_blank_lines(self) -> None:
        result = parse("\n\n\n")
        assert result.lines == []
        assert result.nc is None

    def test_whitespace_only_lines_discarded(self) -> None:
        result = parse("p: Alice\n   \n  \np: Bob")
        assert len(result.lines) == 2


# ── Case insensitivity ──────────────────────────────────────────


class TestCaseInsensitivity:
    """Prefix matching is case-insensitive."""

    def test_uppercase_person(self) -> None:
        result = parse("PERSON: Jane Doe")
        assert result.lines == [ParsedLine(canonical_key="p", text="Jane Doe")]

    def test_mixed_case_tech(self) -> None:
        result = parse("Tech: React")
        assert result.lines == [ParsedLine(canonical_key="t", text="React")]

    def test_uppercase_nc(self) -> None:
        result = parse("NC: Big Corp")
        assert result.nc == "Big Corp"
        assert result.lines == []

    def test_mixed_case_who(self) -> None:
        result = parse("WHO: Bob")
        assert result.who == "Bob"

    def test_uppercase_rel(self) -> None:
        result = parse("REL: Alice > Bob")
        assert result.lines == [
            ParsedLine(canonical_key="rel", text="Alice > Bob")
        ]


# ── Whitespace handling ─────────────────────────────────────────


class TestWhitespaceHandling:
    """Content after colon is stripped; prefix spacing works."""

    def test_no_space_after_colon(self) -> None:
        result = parse("tech:Kubernetes")
        assert result.lines == [ParsedLine(canonical_key="t", text="Kubernetes")]

    def test_extra_spaces_after_colon(self) -> None:
        result = parse("tech:   Kubernetes   ")
        assert result.lines == [ParsedLine(canonical_key="t", text="Kubernetes")]

    def test_leading_whitespace_on_line(self) -> None:
        """Leading whitespace on the line should be handled — the line is
        stripped before prefix matching."""
        result = parse("  tech: Kubernetes")
        assert result.lines == [ParsedLine(canonical_key="t", text="Kubernetes")]

    def test_routing_value_stripped(self) -> None:
        result = parse("nc:   Acme Corp   ")
        assert result.nc == "Acme Corp"

    def test_metadata_value_stripped(self) -> None:
        result = parse("who:   Jane Smith   ")
        assert result.who == "Jane Smith"


# ── Document order preserved ────────────────────────────────────


class TestDocumentOrder:
    """Lines are emitted in document order."""

    def test_order_preserved(self) -> None:
        text = "p: Alice\nfn: Engineering\nt: Python\nkp: tech debt"
        result = parse(text)
        assert [line.canonical_key for line in result.lines] == [
            "p",
            "fn",
            "t",
            "kp",
        ]
        assert [line.text for line in result.lines] == [
            "Alice",
            "Engineering",
            "Python",
            "tech debt",
        ]


# ── Full document integration ───────────────────────────────────


class TestFullDocument:
    """Realistic multi-line documents with mixed prefixes."""

    def test_full_document(self) -> None:
        """A realistic document with routing, metadata, content, and blank lines."""
        text = (
            "c: Acme Corp\n"
            "who: Jane Smith\n"
            "date: 2025-03-15\n"
            "src: Q4 interview\n"
            "\n"
            "p: Bob Jones, CTO\n"
            "p: Alice Green, VP Engineering\n"
            "fn: Engineering\n"
            "fn: Product\n"
            "rel: Alice Green > Bob Jones\n"
            "tech: Kubernetes\n"
            "tech: Terraform\n"
            "proc: CI/CD pipeline\n"
            "cs: rapid growth phase\n"
            "gw: strong engineering culture\n"
            "kp: tech debt in payments\n"
            "rm: cloud migration Q3\n"
            "aop: AI analytics opportunity\n"
            "+: market leader\n"
            "-: limited intl presence\n"
            "opp: EU expansion\n"
            "threat: new competitor\n"
            "a: schedule follow-up\n"
            "This is an untagged line\n"
        )
        result = parse(text)

        # Routing
        assert result.c == "Acme Corp"
        assert result.nc is None
        assert result.cid is None

        # Metadata
        assert result.who == "Jane Smith"
        assert result.date == "2025-03-15"
        assert result.src == "Q4 interview"

        # Lines: 14 prefixed content + 4 SWOT + 1 untagged = 19
        assert len(result.lines) == 19
        assert result.lines[0] == ParsedLine(canonical_key="p", text="Bob Jones, CTO")
        assert result.lines[1] == ParsedLine(
            canonical_key="p", text="Alice Green, VP Engineering"
        )
        assert result.lines[2] == ParsedLine(canonical_key="fn", text="Engineering")
        assert result.lines[3] == ParsedLine(canonical_key="fn", text="Product")
        assert result.lines[4] == ParsedLine(
            canonical_key="rel", text="Alice Green > Bob Jones"
        )
        assert result.lines[5] == ParsedLine(canonical_key="t", text="Kubernetes")
        assert result.lines[6] == ParsedLine(canonical_key="t", text="Terraform")
        assert result.lines[7] == ParsedLine(
            canonical_key="proc", text="CI/CD pipeline"
        )
        assert result.lines[8] == ParsedLine(
            canonical_key="cs", text="rapid growth phase"
        )
        assert result.lines[9] == ParsedLine(
            canonical_key="gw", text="strong engineering culture"
        )
        assert result.lines[10] == ParsedLine(
            canonical_key="kp", text="tech debt in payments"
        )
        assert result.lines[11] == ParsedLine(
            canonical_key="rm", text="cloud migration Q3"
        )
        assert result.lines[12] == ParsedLine(
            canonical_key="aop", text="AI analytics opportunity"
        )
        assert result.lines[13] == ParsedLine(canonical_key="s", text="market leader")
        assert result.lines[14] == ParsedLine(
            canonical_key="w", text="limited intl presence"
        )
        assert result.lines[15] == ParsedLine(canonical_key="o", text="EU expansion")
        assert result.lines[16] == ParsedLine(
            canonical_key="th", text="new competitor"
        )
        assert result.lines[17] == ParsedLine(
            canonical_key="a", text="schedule follow-up"
        )
        assert result.lines[18] == ParsedLine(
            canonical_key="n", text="This is an untagged line"
        )

    def test_no_routing_no_metadata(self) -> None:
        """Document with content only — no routing or metadata."""
        text = "p: Alice\nfn: Engineering\nt: Python"
        result = parse(text)
        assert result.nc is None
        assert result.c is None
        assert result.cid is None
        assert result.who is None
        assert result.date is None
        assert result.src is None
        assert len(result.lines) == 3

    def test_empty_input(self) -> None:
        result = parse("")
        assert result == ParsedSource()

    def test_mixed_valid_invalid_untagged(self) -> None:
        """Mix of valid prefixes, unrecognized prefixes, and no-prefix lines."""
        text = (
            "p: Alice\n"
            "xyz: unknown tag\n"
            "Just some plain text\n"
            "fn: Engineering\n"
        )
        result = parse(text)
        assert len(result.lines) == 4
        assert result.lines[0] == ParsedLine(canonical_key="p", text="Alice")
        assert result.lines[1] == ParsedLine(
            canonical_key="n", text="xyz: unknown tag"
        )
        assert result.lines[2] == ParsedLine(
            canonical_key="n", text="Just some plain text"
        )
        assert result.lines[3] == ParsedLine(canonical_key="fn", text="Engineering")


# ── Edge cases ──────────────────────────────────────────────────


class TestEdgeCases:
    """Various edge cases."""

    def test_colon_in_value(self) -> None:
        """Colons in the value portion should be preserved."""
        result = parse("p: Time: 3:00 PM with Jane")
        assert result.lines == [
            ParsedLine(canonical_key="p", text="Time: 3:00 PM with Jane")
        ]

    def test_empty_value_after_prefix(self) -> None:
        """Prefix with nothing after the colon."""
        result = parse("p:")
        assert result.lines == [ParsedLine(canonical_key="p", text="")]

    def test_empty_value_routing(self) -> None:
        """Routing prefix with empty value."""
        result = parse("nc:")
        assert result.nc == ""

    def test_empty_value_metadata(self) -> None:
        """Metadata prefix with empty value."""
        result = parse("who:")
        assert result.who == ""

    def test_later_routing_overwrites_earlier(self) -> None:
        """If the same routing key appears twice, later value wins."""
        result = parse("nc: First Corp\nnc: Second Corp")
        assert result.nc == "Second Corp"

    def test_later_metadata_overwrites_earlier(self) -> None:
        """If the same metadata key appears twice, later value wins."""
        result = parse("who: Alice\nwho: Bob")
        assert result.who == "Bob"

    def test_url_in_line_not_treated_as_prefix(self) -> None:
        """A line like 'https://example.com' has 'https' before the colon.
        'https' is not in the canonical map so it becomes n: with full line."""
        result = parse("https://example.com/path")
        assert result.lines == [
            ParsedLine(canonical_key="n", text="https://example.com/path")
        ]
