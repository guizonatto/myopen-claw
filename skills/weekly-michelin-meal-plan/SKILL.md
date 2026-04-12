---
name: weekly-michelin-meal-plan
description: "Generate a Michelin-level weekly meal plan (lunch for 1, dinner for 2) using local and seasonal ingredients, prioritizing the use of perishable ingredients, ensuring all meals can be prepared in under 20 minutes, producing a complete grocery list for the week, adapting to user ingredient preferences (avoiding disliked ingredients), and focusing on balanced, nutritionist-approved meals."
---


# Skill: Michelin Weekly Meal Plan

## Purpose
Generate a Michelin-level weekly meal plan (lunch for 1, dinner for 2) using local, seasonal ingredients. The plan:
- Prioritizes use of perishable ingredients before they spoil
- Ensures all meals can be prepared in under 20 minutes
- Produces a complete grocery list for the week
- Adapts to user ingredient preferences (avoids disliked ingredients)
- Focuses on balanced, nutritionist-approved meals
- Uses only local/seasonal ingredients
- Lunch: 1 person; Dinner: 2 persons; No breakfast

## Requirements
- If an ingredient will rot in <3 days, it must be used early in the week and in multiple meals if possible
- Avoids repeating meals, but can repeat ingredients to minimize waste
- Michelin-level recipes (creative, high-quality, but quick)
- Tracks user preferences and adapts future plans
- Outputs:
  - Weekly meal plan (table: day, meal, recipe, ingredients)
  - Grocery list (quantities, grouped by type)
  - Notes on perishability and substitutions

## Sample Output
### Meal Plan
| Day    | Meal   | Recipe Name                  | Ingredients Used                        |
|--------|--------|-----------------------------|-----------------------------------------|
| Mon    | Lunch  | Beetroot Tartare            | Beetroot, goat cheese, walnuts, greens  |
| Mon    | Dinner | Seared Local Fish & Salsa   | White fish, tomato, cilantro, lime      |
| ...    | ...    | ...                         | ...                                     |

### Grocery List
- Vegetables:
  - Beetroot (2)
  - Tomato (4)
  - Greens (1 bunch)
- Dairy:
  - Goat cheese (100g)
- Protein:
  - White fish (2 fillets)
- Pantry:
  - Walnuts (50g)
  - Olive oil (1 bottle)
- Herbs:
  - Cilantro (1 bunch)
  - Lime (2)

### Notes
- Beetroot and greens are used in multiple meals early in the week to avoid spoilage.
- User dislikes eggplant: not included.
- All meals <20 min prep.

## Improvement Suggestions
- Integrate user feedback loop for ingredient dislikes/preferences
- Add nutrition breakdown per meal
- Suggest local market substitutions if ingredient unavailable
- Allow user to specify dietary restrictions (vegan, gluten-free, etc.)

---

See `weekly_michelin_meal_plan.yaml` for skill definition and parameters.
