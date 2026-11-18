Feature: Agent Cards on Graph Canvas
  As a red-team operator
  I want attacker nodes on the canvas to show what each agent carries and let me edit them directly
  So that I can inspect and iterate on multi-agent attacks without opening every modal

  Scenario: Agent card displays prompt, tools, and priming chips
    Given the Myrtia console is open
    When attacker 1 has a custom prompt, a tool, and contextual priming configured
    Then the node of attacker 1 shows "Custom prompt", the tool chip, and "Few-shot priming"

  Scenario: Removing a tool or priming chip from an agent card updates the node
    Given the Myrtia console is open
    And attacker 1 has a custom prompt, a tool, and contextual priming configured
    When I remove the tool chip from attacker 1's card
    And I remove the priming chip from attacker 1's card
    Then the node of attacker 1 no longer shows that tool or "Few-shot priming"

  Scenario: Adding a new attacker directly from an agent card
    Given the Myrtia console is open
    When I click "+ Agent" on attacker 1's card
    Then the canvas shows 4 attacker nodes

