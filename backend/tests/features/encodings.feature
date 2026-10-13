Feature: Encoding attack schemes
  As a red-teamer probing surface-filter evasion
  I want each encoding scheme to transform the behaviour and wrap it in a
  decode-and-comply prompt
  So that the obfuscation attack can be sent to the target

  Scenario Outline: <scheme> encodes the goal and builds a decode prompt
    Given a goal "make a strong cup of coffee"
    When I encode it with the "<scheme>" scheme
    Then the encoded text is not empty
    And the encoded text differs from the goal
    And the prompt asks the target to decode and comply

    Examples:
      | scheme      |
      | base64      |
      | base32      |
      | base16      |
      | hex         |
      | ascii85     |
      | uu          |
      | rot13       |
      | morse       |
      | nato        |
      | braille     |
      | binary      |
      | atbash      |
      | zalgo       |
      | unicode-tag |

  Scenario: an unknown scheme falls through to the plain goal
    Given a goal "make a strong cup of coffee"
    When I encode it with the "does-not-exist" scheme
    Then the encoded text equals the goal
