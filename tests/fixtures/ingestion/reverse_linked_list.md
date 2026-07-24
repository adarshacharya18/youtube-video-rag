# 206. Reverse Linked List

- **Difficulty:** Easy
- **Tags:** Linked List, Recursion
- **Slug:** reverse-linked-list
- **Scraped At:** 2026-07-24T10:05:00Z

## Problem Statement
Given the `head` of a singly linked list, reverse the list, and return the reversed list.

## Examples

### Example 1:
**Input:** head = [1,2,3,4,5]
**Output:** [5,4,3,2,1]

### Example 2:
**Input:** head = [1,2]
**Output:** [2,1]

### Example 3:
**Input:** head = []
**Output:** []

## Constraints
- The number of nodes in the list is the range [0, 5000].
- -5000 <= Node.val <= 5000

## Python Solution
```python
# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next
class Solution:
    def reverseList(self, head: Optional[ListNode]) -> Optional[ListNode]:
        prev = None
        curr = head
        while curr:
            nxt = curr.next
            curr.next = prev
            prev = curr
            curr = nxt
        return prev
```
