# 70. Climbing Stairs

- **Difficulty:** HARD
- **Tags:** Math, Dynamic Programming
- **Slug:** climbing-stairs
- **Scraped At:** 2026-07-24T10:20:00Z

## Task Overview
You are climbing a staircase. It takes `n` steps to reach the top.
Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top?

## Sample Test Cases

Input: n = 2
Output: 2
Explanation: There are two ways to climb to the top. 1. 1 step + 1 step 2. 2 steps

Input: n = 3
Output: 3
Explanation: 1+1+1, 1+2, 2+1.

## Rules & Constraints
- 1 <= n <= 45

## C++ Implementation
```cpp
class Solution {
public:
    int climbStairs(int n) {
        if (n <= 2) return n;
        int a = 1, b = 2;
        for (int i = 3; i <= n; ++i) {
            int c = a + b;
            a = b;
            b = c;
        }
        return b;
    }
};
```
