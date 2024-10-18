from flask import Flask, request, jsonify
import xml.etree.ElementTree as ET

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload_data():
    if request.content_type == 'application/json':
        data = request.json
        return jsonify({"status": "success", "message": "JSON received", "data": data}), 200
    elif request.content_type == 'application/xml':
        try:
            xml_data = ET.fromstring(request.data)
            data_dict = {child.tag: child.text for child in xml_data}
            return jsonify({"status": "success", "message": "XML received", "data": data_dict}), 200
        except ET.ParseError:
            return jsonify({"status": "error", "message": "Invalid XML"}), 400
    else:
        return jsonify({"status": "error", "message": "Unsupported content type"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
