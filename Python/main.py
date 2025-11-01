from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/data/<path:resource>', methods=['POST'])
def handle_all(resource):
    
    # Extract headers
    headers = {
        'user_agent': request.headers.get('User-Agent'),
        'content_type': request.headers.get('Content-Type')
    }
    # Get all headers as dictionary
    all_headers = dict(request.headers)
    
    # Extract query params
    query = request.args.get('q')
    query_params = request.args.to_dict()
    
    # Extract body data
    body_data = request.get_json()
    
    # Extract form data
    form_data = request.form.to_dict()
    
    return jsonify({
        'method': request.method,
        'resource': resource,
        'headers': headers,
        'query_params': query_params,
        'body_data': body_data,
        'form_data': form_data
    })

if __name__ == '__main__':
    app.run(debug=True)