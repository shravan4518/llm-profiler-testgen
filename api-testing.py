from google import genai

client = genai.Client(api_key="AIzaSyA3IVjnHQfLXvpajpQLe_ar7G2-w0jAjMo")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="what is ivanti's profiler"
)

print(response.text)