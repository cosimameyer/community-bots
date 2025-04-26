"""Script to check for length of content"""
import json
import sys

# Function to load JSON data from a file
def load_json(filename):
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: The file '{filename}' contains invalid JSON.")
        return None

# Function to check if the combined length of name, description, and wiki_link exceeds 500 characters
def check_entries(data):
    if not data:
        return
    
    for entry in data:
        # Combine name, description, and wiki_link fields
        combined_text = ""
        combined_text += f"Let's meet {entry.get('name', '')} ✨\n\n{entry.get('description', '')}\n\n🔗 {entry.get('wiki_link', '')}"
        combined_text += f"\n\n#amazingwomeninstem #womeninstem #womenalsoknow #impactthefuture"
        
        # Check the length of the combined text
        if len(combined_text) > 500:
            print(f"🚨 Alert: The combined text for '{entry.get('name', 'Unknown')}' exceeds 500 characters!")
            print(f"Combined length: {len(combined_text)} characters.")
            print(combined_text)
            print(f"Length of description: {len(entry.get('description', ''))}.")
            sys.exit(1)  # Exit with an error code to indicate failure
        

# Main function to load the JSON file and perform the check
def main():
    filename = 'events.json'  # The path to your JSON file
    data = load_json(filename)
    
    if data:
        check_entries(data)
        
    print("All good! 🎉")

if __name__ == '__main__':
    main()