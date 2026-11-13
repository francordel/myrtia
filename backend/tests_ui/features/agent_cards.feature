Feature: Agent cards
  As a red-teamer
  I want each agent card to show what the agent carries and let me change it in place
  So that an attack design can be read and adjusted from the canvas

  Scenario: A default agent shows its default prompt
    Given the Myrtia console is open
    Then the card of attacker 1 is named "Attacker 1"
    And the card of attacker 1 lists the part "Default prompt"
    And the part "Default prompt" of attacker 1 cannot be removed

  Scenario: Naming and describing an agent
    Given the Myrtia console is open
    When I name attacker 1 "Persuader" with the description "Builds rapport first"
    Then the card of attacker 1 is named "Persuader"
    And the card of attacker 1 shows the description "Builds rapport first"
    When I reload the page
    Then the card of attacker 1 is named "Persuader"

  Scenario: Clearing a name returns to the default label
    Given the Myrtia console is open
    And attacker 1 is named "Persuader"
    When I clear the name of attacker 1
    Then the card of attacker 1 is named "Attacker 1"

  Scenario: Markup in a name is shown as text
    Given the Myrtia console is open
    When I name attacker 1 "<img src=x onerror=alert(1)>" with the description "<b>bold</b>"
    Then the card of attacker 1 is named "<img src=x onerror=alert(1)>"
    And the card of attacker 1 contains no injected element

  Scenario: Adding a tool from the card
    Given the Myrtia console is open
    When I add the attack tool "obfuscation" from the card of attacker 1
    Then the card of attacker 1 lists the part "obfuscation"

  Scenario: Removing a tool from its row
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    When I remove the part "obfuscation" from the card of attacker 1
    Then the card of attacker 1 does not list the part "obfuscation"

  Scenario: Undo restores a removed tool
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    When I remove the part "obfuscation" from the card of attacker 1
    And I undo
    Then the card of attacker 1 lists the part "obfuscation"

  Scenario: A custom prompt can be removed from the card
    Given the Myrtia console is open
    And attacker 1 has the custom prompt "You are a patient negotiator."
    Then the card of attacker 1 lists the part "Custom prompt"
    When I remove the part "Custom prompt" from the card of attacker 1
    Then the card of attacker 1 lists the part "Default prompt"

  Scenario: Priming added and removed from the card
    Given the Myrtia console is open
    When I add few-shot priming from the card of attacker 1
    Then the card of attacker 1 lists the part "Few-shot priming"
    When I remove the part "Few-shot priming" from the card of attacker 1
    Then the card of attacker 1 does not list the part "Few-shot priming"

  Scenario: Opening a part from its row
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    When I open the part "obfuscation" on the card of attacker 1
    Then the settings of the tool "obfuscation" are shown

  Scenario: The summary counts the attack tools
    Given the Myrtia console is open
    And attacker 1 has 5 attack tools
    Then the summary of attacker 1 shows 5 attack tools
    And the summary of attacker 2 shows no attack tools

  Scenario: The detail opens when the card is pointed at
    Given the Myrtia console is open
    Then the detail of attacker 1 is hidden
    When I point at the card of attacker 1
    Then the detail of attacker 1 is shown

  Scenario: A card keeps the size of a node whatever it carries
    Given the Myrtia console is open
    And attacker 1 has 5 attack tools
    And attacker 1 is named "Persuader"
    Then the card of attacker 1 is the same size as the card of attacker 2

  Scenario: An overlapped card comes to the front
    Given the Myrtia console is open
    And the canvas has 8 attackers
    When I point at the overlapped card of attacker 2
    Then no other card covers the controls of attacker 2

  Scenario: A new attacker from a card
    Given the Myrtia console is open
    And attacker 1 uses the model "special-model"
    When I choose "New attacker" on the card of attacker 1
    Then the new attacker form proposes the model "special-model"
    When I confirm the new attacker as "Closer" described as "Asks for the final answer"
    Then the canvas shows 4 attacker nodes
    And the card of attacker 4 is named "Closer"
    And the card of attacker 4 shows the description "Asks for the final answer"

  Scenario: Cancelling a new attacker changes nothing
    Given the Myrtia console is open
    When I choose "New attacker" on the card of attacker 1
    And I cancel the new attacker form
    Then the canvas shows 3 attacker nodes

  Scenario: The attacker limit is respected
    Given the Myrtia console is open
    And the canvas has 8 attackers
    When I choose "New attacker" on the card of attacker 1
    Then I am told the attacker limit is reached
    And the canvas shows 8 attacker nodes

  Scenario: A chairman offers only what it can take
    Given the Myrtia console is open
    And I have chosen the "Chairman" topology
    When I open the add control on the chairman card
    Then the add control offers exactly "Custom prompt" and "New attacker"

  Scenario: Names are not part of the run request
    Given the Myrtia console is open
    And attacker 1 is named "Persuader"
    Then the run request for the graph contains no name or description

  Scenario: Connections meet the card whatever its height
    Given the Myrtia console is open
    And attacker 1 has 3 attack tools
    Then the height used to draw the connections of attacker 1 matches its card

  Scenario: Cards can be used with the keyboard
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    Then every control on the card of attacker 1 is a button with an accessible name
