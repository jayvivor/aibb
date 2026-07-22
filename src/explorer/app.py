import threading

from flask import Flask, jsonify, render_template, request

from explorer import helpers, replay
from explorer.house import ExplorerHouse, SimStopped


app = Flask(__name__)

sim = {
    "house": helpers.get_explorer_house(),
    "thread": None,
    "running": False,
    "error": None,
}


def run_season(house: ExplorerHouse):
    try:
        house.simulate_season()
    except SimStopped:
        pass
    except Exception as error:
        sim["error"] = f"{type(error).__name__}: {error}"
    finally:
        sim["running"] = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/season")
def season():
    return jsonify(replay.get_season_info(sim["house"]))


@app.route("/api/status")
def status():
    items = replay.get_history_items(sim["house"])
    return jsonify({
        "running": sim["running"],
        "error": sim["error"],
        "max_index": items[-1][0].index if items else 0,
        "marks": replay.get_marks(sim["house"]),
    })


@app.route("/api/run", methods=["POST"])
def run():
    if sim["running"]:
        return jsonify({"error": "A season is already running."}), 409
    if sim["house"].history or (request.json and request.json.get("fresh")):
        sim["house"] = helpers.get_explorer_house()
    sim["error"] = None
    sim["running"] = True
    sim["thread"] = threading.Thread(target=run_season, args=(sim["house"],), daemon=True)
    sim["thread"].start()
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def stop():
    sim["house"].stop_requested = True
    return jsonify({"ok": True})


@app.route("/api/turn/<int:index>")
def turn(index: int):
    return jsonify(replay.get_turn(sim["house"], index))


@app.route("/api/houseguest/<name>")
def houseguest(name: str):
    upto = request.args.get("upto", default=0, type=int)
    return jsonify({"name": name} | replay.get_houseguest_history(sim["house"], name, upto))


@app.route("/api/room/<name>")
def room(name: str):
    upto = request.args.get("upto", default=0, type=int)
    return jsonify({"name": name} | replay.get_room_history(sim["house"], name, upto))


if __name__ == "__main__":
    app.run(debug=False, port=5001, threaded=True)
