import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import httpx
import chardet
import numpy as np
from pathlib import Path

# Constants
API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

# Ensure token is retrieved from environment variable
def get_token():
    try:
        return os.environ["AIPROXY_TOKEN"]
    except KeyError:
        print("Error: AIPROXY_TOKEN environment variable not set.")
        sys.exit(1)

def load_data(file_path):
    """Load CSV data with encoding detection."""
    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    encoding = result['encoding']
    print(f"Detected file encoding: {encoding}")
    return pd.read_csv(file_path, encoding=encoding)

def generate_narrative(analysis, token, file_path):
    """Generate narrative using LLM."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    prompt = (
        f"You are a data analyst. Provide a detailed narrative based on the following data analysis results for the file '{file_path.name}':\n\n"
        f"Column Names & Types: {list(analysis['summary'].keys())}\n\n"
        f"Summary Statistics: {analysis['summary']}\n\n"
        f"Missing Values: {analysis['missing_values']}\n\n"
        f"Correlation Matrix: {analysis['correlation']}\n\n"
        "Suggest insights, trends, and additional analyses like clustering or anomaly detection."
    )
    
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = httpx.post(API_URL, headers=headers, json=data, timeout=30.0)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error generating narrative: {e}")
        return "Narrative generation failed due to an error."

def analyze_data(df, token):
    """Perform basic data analysis and request LLM suggestions."""
    if df.empty:
        print("Error: Dataset is empty.")
        sys.exit(1)

    numeric_df = df.select_dtypes(include=['number'])
    categorical_df = df.select_dtypes(include=['object', 'category'])

    analysis = {
        'summary': df.describe(include='all').to_dict(),
        'missing_values': df.isnull().sum().to_dict(),
        'correlation': numeric_df.corr().to_dict() if not numeric_df.empty else {},
        'categorical_summary': {col: df[col].value_counts().to_dict() for col in categorical_df.columns}
    }
    print("Data analysis complete.")
    
    # Example LLM request for suggestions
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    prompt = (
        f"Given the dataset with the following summary: {analysis['summary']} and correlations: {analysis['correlation']}, "
        "suggest additional analyses or improvements."
    )
    try:
        response = httpx.post(API_URL, headers=headers, json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}, timeout=30.0)
        response.raise_for_status()
        suggestions = response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error fetching analysis suggestions: {e}")
        suggestions = "No suggestions available."
    
    return analysis, suggestions

def visualize_data(df, output_dir, analysis):
    """Generate and save visualizations."""
    sns.set(style="whitegrid")
    numeric_columns = df.select_dtypes(include=['number']).columns
    categorical_columns = df.select_dtypes(include=['object', 'category']).columns
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    if not numeric_columns.empty:
        # Correlation Heatmap
        corr = df[numeric_columns].corr()
        plt.figure(figsize=(8, 8))
        sns.heatmap(corr, annot=True, cmap='coolwarm', square=True)
        plt.title('Correlation Heatmap')
        heatmap_path = output_dir / "correlation_heatmap.png"
        plt.savefig(heatmap_path)
        print(f"Saved correlation heatmap to {heatmap_path}")
        plt.close()

    if not categorical_columns.empty:
    # Ensure at least one numerical column exists
        numeric_columns = df.select_dtypes(include=['number']).columns
        if numeric_columns.empty:
            raise ValueError("No numerical columns found for scatter plot.")

    for col in categorical_columns[:2]:  # Only the first two categorical columns
        for num_col in numeric_columns[:1]:  # Use the first numerical column for scatter plot
            plt.figure(figsize=(10, 6))
            sns.scatterplot(data=df, x=col, y=num_col, hue=col, palette="Set2", s=100, alpha=0.7)
            plt.title(f"Scatter Plot of {num_col} vs {col}")
            scatterplot_path = output_dir / f"{col}_scatter_plot.png"
            plt.xticks(rotation=45)
            plt.savefig(scatterplot_path)
            print(f"Saved scatter plot of {num_col} vs {col} to {scatterplot_path}")
            plt.close()
    

    # if not categorical_columns.empty:
    #     # Categorical Distribution Bar Plots
    #     for col in categorical_columns[:2]:
    #         plt.figure(figsize=(10, 6))
    #         sns.countplot(data=df, x=col, palette="Set2")
    #         plt.title(f"Distribution of {col}")
    #         catplot_path = output_dir / f"{col}_distribution.png"
    #         plt.xticks(rotation=45)
    #         plt.savefig(catplot_path)
    #         print(f"Saved {col} distribution plot to {catplot_path}")
    #         plt.close()

def save_narrative_with_images(narrative, output_dir):
    """Save narrative to README.md and embed image links."""
    readme_path = output_dir / 'README.md'
    image_links = "\n".join(
        [f"![{img.name}]({img.name})" for img in output_dir.glob('*.png')]
    )
    with open(readme_path, 'w') as f:
        f.write(narrative + "\n\n" + image_links)
    print(f"Narrative saved to {readme_path}")

def main(file_path):
    print("Starting autolysis process...")
    file_path = Path(file_path)
    if not file_path.is_file():
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)

    token = get_token()
    df = load_data(file_path)
    print("Dataset loaded successfully.")

    print("Analyzing data...")
    analysis, suggestions = analyze_data(df, token)
    print(f"Analysis Suggestions: {suggestions}")

    output_dir = Path.cwd() / file_path.stem
    output_dir.mkdir(exist_ok=True)

    print("Generating visualizations...")
    visualize_data(df, output_dir, analysis)

    print("Generating narrative...")
    narrative = generate_narrative(analysis, token, file_path)
    save_narrative_with_images(narrative, output_dir)

    print(f"Process completed. Outputs saved in: {output_dir}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <file_path>")
        sys.exit(1)
    main(sys.argv[1])
