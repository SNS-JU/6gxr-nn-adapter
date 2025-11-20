from flask import Flask, Response, request, jsonify
from flask_cors import cross_origin
from experiment import Experiment
import logging
import json

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

app = Flask(__name__)
exp = Experiment()

@app.route("/", methods=["GET"])
@cross_origin()
def root():
    return "North Node Adapter API"

@app.route("/experiment", methods=["GET"])
@cross_origin()
def experimentAllRead():
    status = exp.getStatus()

    if status["id"] == None:
        return jsonify([])

    return jsonify([
        {"id": status["id"], "state": status["state"], "message": status["message"]}
    ])

@app.route("/experiment/<int:id>", methods=["GET"])
@cross_origin()
def experimentRead(id):
    status = exp.getStatus()

    if status["id"] != id:
        return "Experiment not found!", 404

    return jsonify({"id": status["id"], "state": status["state"], "message": status["message"]})

@app.route("/experiment", methods=["POST"])
@cross_origin()
def experimentCreate():
    retval = None

    try:
        retval = exp.start(json.loads(request.form.get("nst")))
    except Exception as e:
        return str(e), 400

    return jsonify(retval)

@app.route("/experiment/<int:id>", methods=["DELETE"])
@cross_origin()
def experimentDelete(id):
    log = ""

    try:
        log = exp.stop(id)
    except Exception as e:
        return str(e), 404

    resp = Response(response=log, status=200, mimetype="text/plain")
    resp.headers["Content-Type"] = "text/plain; charset=us-ascii"

    return resp

if __name__ == "__main__":
    app.run(port=5000, host="::", debug=True, threaded=True, use_reloader=False)
