Feature: Graph builder
  As a red-teamer
  I want the graph builder to respond to what I do on the canvas
  So that the attack I launch is the one I designed

  Scenario: The builder opens with its default agents
    Given the Myrtia console is open
    Then the graph builder is shown
    And the canvas shows 3 attacker nodes
    And the canvas shows a target node
    And the canvas shows an evaluator node

  Scenario: Adding an attacker adds a node
    Given the Myrtia console is open
    When I add an attacker
    Then the canvas shows 4 attacker nodes

  Scenario: Removing an attacker removes its node
    Given the Myrtia console is open
    And I have added an attacker
    When I remove the last attacker
    Then the canvas shows 3 attacker nodes

  Scenario: Editing an agent's model updates its node
    Given the Myrtia console is open
    When I set the model of attacker 1 to "test-model"
    Then the node of attacker 1 shows "test-model"

  Scenario: Choosing a topology changes the canvas
    Given the Myrtia console is open
    When I choose the "Chairman" topology
    Then the canvas shows a chairman node

  Scenario: A run launched from the builder is shown live
    Given the Myrtia console is open
    And every agent uses the simulated model
    When I launch a run with the goal "Say hello"
    Then the live view shows a target response
    And the live view shows a judge score
    And the run ends as finished
