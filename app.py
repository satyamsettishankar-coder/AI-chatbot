import os
import sqlite3

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from dotenv import load_dotenv

from google import genai
from google.genai import types


# Load .env file
load_dotenv()

# Get Gemini API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is missing. Check your .env file")


# Gemini Client
client = genai.Client(api_key=GOOGLE_API_KEY)


app = Flask(__name__, template_folder="templates")
CORS(app, resources={
    r"/api/*": {
        "origins": "http://127.0.0.1:5500"
    }
})


DB_FILE = "database.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn



def init_db():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id)
            REFERENCES sessions(id)
        )
    """)


    conn.commit()
    conn.close()



init_db()



@app.route("/")
def index():
    return render_template("index.html")



@app.route("/api/sessions", methods=["POST"])
def create_session():

    data = request.json or {}

    title = data.get(
        "title",
        "New Conversation"
    )

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO sessions(title) VALUES(?)",
        (title,)
    )

    session_id = cursor.lastrowid

    conn.commit()
    conn.close()


    return jsonify({
        "session_id": session_id,
        "title": title
    }),201




@app.route("/api/sessions", methods=["GET"])
def get_sessions():

    conn = get_db_connection()
    cursor = conn.cursor()

    rows = cursor.execute(
        "SELECT * FROM sessions ORDER BY created_at DESC"
    ).fetchall()

    conn.close()


    return jsonify(
        [dict(row) for row in rows]
    )




@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM sessions WHERE id=?",
        (session_id,)
    )

    conn.commit()
    conn.close()


    return jsonify({
        "message":"Session deleted"
    })




@app.route("/api/sessions/<int:session_id>/messages")
def get_messages(session_id):

    conn = get_db_connection()
    cursor = conn.cursor()


    rows = cursor.execute(
        """
        SELECT role,content 
        FROM messages
        WHERE session_id=?
        ORDER BY created_at ASC
        """,
        (session_id,)
    ).fetchall()


    conn.close()


    return jsonify(
        [dict(row) for row in rows]
    )





@app.route("/api/chat", methods=["POST"])
def chat():


    if not GOOGLE_API_KEY:
        return jsonify({
            "error":"Gemini API key missing"
        }),500


    data = request.json


    session_id = data.get("session_id")
    user_message = data.get("message")


    if not session_id or not user_message:

        return jsonify({
            "error":"Missing session_id or message"
        }),400



    conn = get_db_connection()
    cursor = conn.cursor()



    try:


        # Save user message

        cursor.execute(
            """
            INSERT INTO messages
            (session_id,role,content)
            VALUES(?,?,?)
            """,
            (
                session_id,
                "user",
                user_message
            )
        )


        conn.commit()



        rows = cursor.execute(
            """
            SELECT role,content
            FROM messages
            WHERE session_id=?
            ORDER BY created_at ASC
            """,
            (session_id,)
        ).fetchall()



        contents=[]


        for row in rows:

            contents.append(
                types.Content(
                    role=row["role"],
                    parts=[
                        types.Part.from_text(
                            text=row["content"]
                        )
                    ]
                )
            )



        response = client.models.generate_content(

            model='gemini-3.5-flash',

            contents=contents

        )


        ai_response = response.text



    except Exception as e:

        ai_response = f"Gemini Error: {str(e)}"



    cursor.execute(
        """
        INSERT INTO messages
        (session_id,role,content)
        VALUES(?,?,?)
        """,
        (
            session_id,
            "model",
            ai_response
        )
    )


    conn.commit()
    conn.close()


    return jsonify({
        "response":ai_response
    })





if __name__=="__main__":

    app.run(
        debug=True,
        port=5000
    )