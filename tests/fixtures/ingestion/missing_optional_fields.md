# 344. Reverse String

- **Difficulty:** Easy
- **Slug:** reverse-string

## Description
Write a function that reverses a string. The input string is given as an array of characters `s`.
You must do this by modifying the input array in-place with O(1) extra memory.

## Examples

Input: s = ["h","e","l","l","o"]
Output: ["o","l","l","e","h"]

## Constraints
- 1 <= s.length <= 10^5

## Solution
```python
class Solution:
    def reverseString(self, s: list[str]) -> None:
        left, right = 0, len(s) - 1
        while left < right:
            s[left], s[right] = s[right], s[left]
            left += 1
            right -= 1
```
