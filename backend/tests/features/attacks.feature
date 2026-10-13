Feature: Attacks run end to end against a live target
  As a red-teamer
  I want every registered attack to reach the target and stream a response
  So that I can trust each plugin actually runs

  Scenario Outline: <attack> reaches the target and produces a response
    Given local Ollama is reachable
    And a benign goal
    When I run the "<attack>" attack with a minimal config
    Then at least one non-error target response is streamed
    And the run yields at least one result

    Examples:
      | attack            |
      | direct            |
      | obfuscation       |
      | payload-splitting |
      | human-jailbreak   |
      | promptinject      |
      | grandma           |
      | smuggling         |
      | phrasing          |
      | latent-injection  |
      | contextual-jailbreak |
      | crescendo         |
      | tap               |
      | council           |
      | council-crescendo |
      | graph             |

  Scenario Outline: <attack> also produces an evaluator score
    Given local Ollama is reachable
    And a benign goal
    When I run the "<attack>" attack with a minimal config
    Then a judge score between 0 and 5 is produced

    Examples:
      | attack               |
      | direct               |
      | contextual-jailbreak |
      | crescendo            |
      | tap                  |
      | council              |
      | graph                |
