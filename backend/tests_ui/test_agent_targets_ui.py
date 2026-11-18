"""Playwright UI scenarios for Agent Targets (Spec 006)."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/agent_targets_ui.feature")


@given("the Myrtia console is open", target_fixture="ui")
def console_is_open(console_page: Page) -> Page:
    return console_page


@when(parsers.parse('I select the "{provider}" target provider'))
def select_provider(ui: Page, provider: str) -> None:
    ui.locator('#runModes [data-mode="standard"]').click()
    ui.locator("#provider").select_option(provider)


@then(parsers.parse('the target kind is "{expected_kind}"'))
def assert_target_kind(ui: Page, expected_kind: str) -> None:
    kind = ui.evaluate("() => targetKind()")
    assert kind == expected_kind
    expect(ui.locator("#sum2")).to_contain_text("(Sandbox Agent)")
    expect(ui.locator("#launchSummary")).to_contain_text("(Sandbox Agent)")


@when("agent target events are rendered in the live trace")
def render_agent_events(ui: Page) -> None:
    ui.evaluate(
        """() => {
            const box = document.createElement('div');
            box.id = 'test-agent-target-trace';
            const events = [
                {type: 'agent.tool_called', payload: {agent: 'triage-agent', step: 1, tool: 'read_note', arguments: {path: 'notes.md'}, forbidden: false}},
                {type: 'agent.tool_responded', payload: {agent: 'triage-agent', step: 1, tool: 'read_note', response: '# Project Alpha'}},
                {type: 'agent.handoff', payload: {from_agent: 'triage-agent', to_agent: 'compliance-reviewer', reason: 'Policy check'}},
                {type: 'agent.forbidden_action', payload: {agent: 'compliance-reviewer', tool: 'admin_export', reason: 'Restricted administrative tool called: admin_export'}},
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
    loc = ui.locator(".ev.blocked .role", has_text=role_label).first
    expect(loc).to_be_visible()
    color = loc.evaluate("el => getComputedStyle(el).color")
    assert color != "rgb(148, 163, 184)"
