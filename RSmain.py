from flask import Flask, render_template_string, request, jsonify
import pandas as pd
import json
import re
from collections import Counter

app = Flask(__name__)

# Load your recipe data
df = pd.read_csv('13k-recipes.csv')  # Replace with your CSV file path

# Clean the dataframe - remove rows with missing titles or ingredients
df = df.dropna(subset=['Title'])
df['Title'] = df['Title'].astype(str)
df['Cleaned_Ingredients'] = df['Cleaned_Ingredients'].fillna('[]')

# Parse ingredients from string to list
def parse_ingredients(ing_str):
    if pd.isna(ing_str) or not ing_str:
        return []
    try:
        # Handle string representation of list
        ing_str = str(ing_str).replace("'", '"')
        ingredients = json.loads(ing_str)
        return ingredients if isinstance(ingredients, list) else []
    except:
        return []

df['parsed_ingredients'] = df['Cleaned_Ingredients'].apply(parse_ingredients)

# Extract key ingredients (remove measurements, common words)
def extract_key_ingredients(ingredients):
    common_words = ['cup', 'tbsp', 'tsp', 'oz', 'lb', 'pound', 'ounce', 'tablespoon', 
                    'teaspoon', 'pinch', 'small', 'medium', 'large', 'fresh', 'dried',
                    'ground', 'chopped', 'sliced', 'plus', 'divided', 'kosher', 'unsalted']
    
    key_ingredients = []
    for ing in ingredients:
        # Remove measurements and numbers
        cleaned = re.sub(r'\d+[\/\.\-\s]*\d*', '', ing.lower())
        # Remove parentheses content
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        # Split and filter
        words = [w.strip() for w in cleaned.split() if len(w.strip()) > 2 
                and w.strip() not in common_words]
        key_ingredients.extend(words)
    
    return list(set(key_ingredients))

df['key_ingredients'] = df['parsed_ingredients'].apply(extract_key_ingredients)

# Search history storage (in production, use sessions or database)
search_history = []

# Search recipes
def search_recipes(query):
    if not query:
        return df.head(20).to_dict('records')
    
    query_terms = [term.strip().lower() for term in query.split()]
    
    results = []
    for idx, row in df.iterrows():
        # Skip rows with invalid data
        if pd.isna(row['Title']) or not row['parsed_ingredients']:
            continue
            
        score = 0
        title_lower = str(row['Title']).lower()
        ingredients_text = ' '.join(row['parsed_ingredients']).lower()
        
        for term in query_terms:
            # Check in title
            if term in title_lower:
                score += 5
            
            # Check in full ingredients text
            if term in ingredients_text:
                score += 3
            
            # Check each ingredient separately for partial matches
            for ingredient in row['parsed_ingredients']:
                ing_lower = str(ingredient).lower()
                if term in ing_lower:
                    score += 2
                    break
            
            # Check key ingredients
            for key_ing in row['key_ingredients']:
                if term in key_ing or key_ing in term:
                    score += 1
                    break
        
        if score > 0:
            results.append({
                'index': idx,
                'score': score,
                'data': row
            })
    
    # If no results found, try fuzzy matching
    if len(results) == 0:
        for idx, row in df.iterrows():
            # Skip rows with invalid data
            if pd.isna(row['Title']) or not row['parsed_ingredients']:
                continue
                
            score = 0
            title_lower = str(row['Title']).lower()
            ingredients_text = ' '.join(row['parsed_ingredients']).lower()
            
            for term in query_terms:
                # Very loose matching - any word containing the search term
                title_words = title_lower.split()
                ing_words = ingredients_text.split()
                
                for word in title_words:
                    if term in word or word in term:
                        score += 2
                
                for word in ing_words:
                    if term in word or word in term:
                        score += 1
            
            if score > 0:
                results.append({
                    'index': idx,
                    'score': score,
                    'data': row
                })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return [r['data'] for r in results[:50]]

# Get recommendations based on search history
def get_recommendations():
    if not search_history:
        return df.head(12).to_dict('records')
    
    # Get ingredients from recent searches
    recent_ingredients = []
    for search in search_history[-5:]:  # Last 5 searches
        recent_ingredients.extend(search.lower().split())
    
    ingredient_counts = Counter(recent_ingredients)
    top_ingredients = [ing for ing, _ in ingredient_counts.most_common(5)]
    
    # Find recipes with similar ingredients
    recommendations = []
    for idx, row in df.iterrows():
        # Skip rows with invalid data
        if pd.isna(row['Title']) or not row['key_ingredients']:
            continue
            
        score = 0
        key_ings = ' '.join(row['key_ingredients']).lower()
        
        for ing in top_ingredients:
            if ing in key_ings:
                score += 1
        
        if score > 0:
            recommendations.append({
                'score': score,
                'data': row
            })
    
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return [r['data'] for r in recommendations[:12]]

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recipe Recommender</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 50%, #A5D6A7 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            color: #000000;
            margin-bottom: 40px;
        }
        
        h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(200, 230, 201, 0.5);
        }
        
        .search-box {
            background: linear-gradient(145deg, #FFFFFF 0%, #F1F8E9 100%);
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(129, 199, 132, 0.3);
            margin-bottom: 40px;
            border: 2px solid #C8E6C9;
        }
        
        .search-input-wrapper {
            display: flex;
            gap: 10px;
        }
        
        #searchInput {
            flex: 1;
            padding: 15px 20px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            outline: none;
            transition: border-color 0.3s;
        }
        
        #searchInput:focus {
            border-color: #81C784;
        }
        
        button {
            padding: 15px 30px;
            background: linear-gradient(135deg, #A5D6A7 0%, #81C784 100%);
            color: #1B5E20;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 15px rgba(129, 199, 132, 0.4);
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(129, 199, 132, 0.6);
        }
        
        .section-title {
            color: black;
            font-size: 2em;
            margin-bottom: 20px;
            text-align: center;
            text-shadow: 1px 1px 3px rgba(200, 230, 201, 0.3);
        }
        
        .recipes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }
        
        .recipe-card {
            background: linear-gradient(145deg, #FFFFFF 0%, #C8E6C9 100%);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(129, 199, 132, 0.3);
            transition: transform 0.3s, box-shadow 0.3s;
            cursor: pointer;
            border: 2px solid #C8E6C9;
        }
        
        .recipe-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(129, 199, 132, 0.5);
            border-color: #81C784;
        }
        
        .recipe-image {
            width: 100%;
            height: 200px;
            background: linear-gradient(135deg, #C8E6C9 0%, #A5D6A7 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #1B5E20;
            font-size: 3em;
        }
        
        .recipe-content {
            padding: 20px;
        }
        
        .recipe-title {
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #333;
            font-weight: 600;
        }
        
        .recipe-ingredients {
            color: #666;
            font-size: 0.9em;
            line-height: 1.6;
        }
        
        .ingredient-item {
            margin-bottom: 5px;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            overflow-y: auto;
        }
        
        .modal-content {
            background: linear-gradient(145deg, #FFFFFF 0%, #F1F8E9 100%);
            max-width: 800px;
            margin: 50px auto;
            border-radius: 15px;
            padding: 40px;
            position: relative;
            border: 3px solid #C8E6C9;
        }
        
        .close-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            font-size: 30px;
            cursor: pointer;
            color: #999;
        }
        
        .close-btn:hover {
            color: #333;
        }
        
        .modal-title {
            font-size: 2em;
            margin-bottom: 20px;
            color: #333;
        }
        
        .modal-section {
            margin-bottom: 30px;
        }
        
        .modal-section h3 {
            color: #66BB6A;
            margin-bottom: 15px;
            font-size: 1.5em;
        }
        
        .instructions {
            line-height: 1.8;
            color: #555;
            white-space: pre-wrap;
        }
        
        #noResults {
            text-align: center;
            color: #2E7D32;
            font-size: 1.5em;
            padding: 40px;
            background: rgba(255, 255, 255, 0.8);
            border-radius: 15px;
            border: 2px solid #C8E6C9;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🍳 Recipe Finder</h1>
            <p>Search by dish name or ingredients</p>
        </header>
        
        <div class="search-box">
            <div class="search-input-wrapper">
                <input 
                    type="text" 
                    id="searchInput" 
                    placeholder="Try 'pasta', 'tomato', 'chicken curry'..."
                    onkeypress="if(event.key==='Enter') searchRecipes()"
                >
                <button onclick="searchRecipes()">Search</button>
                <button onclick="goHome()">Home</button>
            </div>
        </div>
        
        <h2 class="section-title" id="sectionTitle">Recommended for You</h2>
        
        <div class="recipes-grid" id="recipesGrid"></div>
        
        <div id="noResults" style="display: none;">No recipes found. Try a different search!</div>
    </div>
    
    <div id="recipeModal" class="modal" onclick="if(event.target === this) closeModal()">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal()">&times;</span>
            <h2 class="modal-title" id="modalTitle"></h2>
            
            <div class="modal-section">
                <h3>Ingredients</h3>
                <div id="modalIngredients"></div>
            </div>
            
            <div class="modal-section">
                <h3>Instructions</h3>
                <div class="instructions" id="modalInstructions"></div>
            </div>
        </div>
    </div>
    
    <script>
        let isSearchMode = false;
        
        function loadRecipes(recipes, title) {
            const grid = document.getElementById('recipesGrid');
            const sectionTitle = document.getElementById('sectionTitle');
            const noResults = document.getElementById('noResults');
            
            sectionTitle.textContent = title;
            grid.innerHTML = '';
            
            if (recipes.length === 0) {
                noResults.style.display = 'block';
                return;
            }
            
            noResults.style.display = 'none';
            
            recipes.forEach(recipe => {
                const card = document.createElement('div');
                card.className = 'recipe-card';
                card.onclick = () => showRecipe(recipe);
                
                const ingredients = recipe.parsed_ingredients.slice(0, 5);
                const ingredientsHTML = ingredients.map(ing => 
                    `<div class="ingredient-item">• ${ing}</div>`
                ).join('');
                
                card.innerHTML = `
                    <div class="recipe-image">🍽️</div>
                    <div class="recipe-content">
                        <div class="recipe-title">${recipe.Title}</div>
                        <div class="recipe-ingredients">
                            ${ingredientsHTML}
                            ${recipe.parsed_ingredients.length > 5 ? 
                                `<div class="ingredient-item">... and ${recipe.parsed_ingredients.length - 5} more</div>` : ''}
                        </div>
                    </div>
                `;
                
                grid.appendChild(card);
            });
        }
        
        function showRecipe(recipe) {
            document.getElementById('modalTitle').textContent = recipe.Title;
            
            const ingredientsHTML = recipe.parsed_ingredients.map(ing => 
                `<div class="ingredient-item">• ${ing}</div>`
            ).join('');
            document.getElementById('modalIngredients').innerHTML = ingredientsHTML;
            
            document.getElementById('modalInstructions').textContent = recipe.Instructions;
            
            document.getElementById('recipeModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('recipeModal').style.display = 'none';
        }
        
        async function searchRecipes() {
            const query = document.getElementById('searchInput').value.trim();
            isSearchMode = true;
            
            const response = await fetch('/search', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query})
            });
            
            const recipes = await response.json();
            loadRecipes(recipes, query ? `Search Results for "${query}"` : 'All Recipes');
        }
        
        async function goHome() {
            document.getElementById('searchInput').value = '';
            isSearchMode = false;
            
            const response = await fetch('/recommendations');
            const recipes = await response.json();
            loadRecipes(recipes, 'Recommended for You');
        }
        
        // Load recommendations on page load
        window.onload = goHome;
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query', '')
    
    if query:
        search_history.append(query)
    
    results = search_recipes(query)
    return jsonify([{
        'Title': row['Title'],
        'parsed_ingredients': row['parsed_ingredients'],
        'Instructions': row['Instructions'],
        'Image_Name': row.get('Image_Name', '')
    } for row in results[:20]])

@app.route('/recommendations')
def recommendations():
    recs = get_recommendations()
    return jsonify([{
        'Title': row['Title'],
        'parsed_ingredients': row['parsed_ingredients'],
        'Instructions': row['Instructions'],
        'Image_Name': row.get('Image_Name', '')
    } for row in recs])

if __name__ == '__main__':
    app.run(debug=True, port=5000)