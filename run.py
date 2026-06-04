"""Entry point for the Grammar School Library website."""
from library import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
