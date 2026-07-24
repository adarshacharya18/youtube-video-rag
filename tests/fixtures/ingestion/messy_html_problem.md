# 15. 3Sum

- **Difficulty:** MED
- **Tags:** Array, <b>Two Pointers</b>, Sorting
- **Slug:** 3sum
- **Scraped At:** 2026-07-24T10:15:00Z

## Description
<p>Given an integer array nums, return all the triplets <code>[nums[i], nums[j], nums[k]]</code> such that <code>i &ne; j</code>, <code>i &ne; k</code>, and <code>j &ne; k</code>, and <code>nums[i] + nums[j] + nums[k] == 0</code>.</p>
<p>Notice that the solution set must not contain duplicate triplets. &amp; special characters: &lt;tag&gt; &quot;quote&quot;.</p>

## Examples

### Example 1:
<b>Input:</b> nums = [-1,0,1,2,-1,-4]<br/>
<b>Output:</b> [[-1,-1,2],[-1,0,1]]<br/>
<b>Explanation:</b><br/>
nums[0] + nums[1] + nums[2] = (-1) + 0 + 1 = 0.<br/>
nums[1] + nums[2] + nums[4] = 0 + 1 + (-1) = 0.<br/>
The distinct triplets are [-1,0,1] and [-1,-1,2].

## Constraints
- 3 &lt;= nums.length &lt;= 3000
- -10<sup>5</sup> &lt;= nums[i] &lt;= 10<sup>5</sup>

## Solution Code
```python
class Solution:
    def threeSum(self, nums: list[int]) -> list[list[int]]:
        nums.sort()
        res = []
        for i in range(len(nums) - 2):
            if i > 0 and nums[i] == nums[i-1]:
                continue
            l, r = i + 1, len(nums) - 1
            while l < r:
                s = nums[i] + nums[l] + nums[r]
                if s < 0:
                    l += 1
                elif s > 0:
                    r -= 1
                else:
                    res.append([nums[i], nums[l], nums[r]])
                    while l < r and nums[l] == nums[l+1]:
                        l += 1
                    while l < r and nums[r] == nums[r-1]:
                        r -= 1
                    l += 1
                    r -= 1
        return res
```
