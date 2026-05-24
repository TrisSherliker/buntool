import logging
import os
import shutil
import tempfile
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from colorlog import ColoredFormatter
from flask import Flask, current_app, jsonify, render_template, request, send_file
from waitress import serve
from werkzeug.datastructures import FileStorage

try:
    from flask_livereload import LiveReload
except ImportError:
    LiveReload = None

from buntool import bundle
from buntool.bundle_config import BundleConfigParams

# from buntool.trace_malloc import TraceMalloc

# import boto3

# def upload_to_s3(file_path, s3_key):
#     s3.upload_file(file_path, bucket_name, s3_key)
#     return f"s3://{bucket_name}/{s3_key}"

# app = Flask(__name__) # Will be created by the app factory

# Constants
MAX_FILENAME_LENGTH = 100


@dataclass
class RequestContext:
    """Holds context information for a bundle creation request."""

    session_id: str
    user_agent: str
    timestamp: str
    temp_dir: Path


def is_running_in_lambda():
    return "AWS_LAMBDA_FUNCTION_NAME" in os.environ  # seems to work?


def strtobool(value: str) -> bool:
    value = value.lower()
    return value in ("y", "yes", "on", "1", "true", "t", "True", "enabled")


def get_output_filename(bundle_title: str, case_name: str, timestamp: str, fallback="Bundle"):
    # Takes in the bundle title, case name, and a timestamp.
    # purpose is to guard against extra-long filenames.
    # Returns the output filename picked among many fallback options.
    output_file = f"{bundle_title}_{case_name}_{timestamp}.pdf"
    if len(output_file) > MAX_FILENAME_LENGTH:
        # take first 20 chars of bundle title and add case name:
        output_file = f"{bundle_title[:20]}_{case_name}_{timestamp}.pdf"
    if len(output_file) > MAX_FILENAME_LENGTH:
        # take first 20 chars of bundle title, first 20 chars of case name, and add timestamp:
        output_file = f"{bundle_title[:30]}_{case_name[:30]}_{timestamp}.pdf"
    if len(output_file) > MAX_FILENAME_LENGTH:
        # this should never happen:
        output_file = f"{fallback}_{timestamp}.pdf"
    if len(output_file) > MAX_FILENAME_LENGTH:
        # this should doubly never happen:
        output_file = f"{timestamp}.pdf"
    return output_file


def _get_bundle_config_from_form(form: dict, context: RequestContext, logs_dir: Path):
    """Extracts bundle configuration from the request form."""
    bundle_title = form.get("bundle_title", "Bundle") if form.get("bundle_title") else "Bundle"
    case_name = form.get("case_name")
    claim_no = form.get("claim_no")
    case_details = {"bundle_title": bundle_title, "claim_no": claim_no or "", "case_name": case_name or ""}

    return bundle.BundleConfig(
        BundleConfigParams(
            timestamp=context.timestamp,
            case_details=case_details,
            csv_string="",
            confidential_bool=strtobool(form.get("confidential_bool", "false")),
            zip_bool=True,  # option not implemented for GUI control.
            session_id=context.session_id,
            user_agent=context.user_agent,
            page_num_align=form.get("page_num_align", ""),
            index_font=form.get("index_font", ""),
            footer_font=form.get("footer_font", ""),
            page_num_style=form.get("page_num_style", ""),
            footer_prefix=form.get("footer_prefix", ""),
            date_setting=form.get("date_setting", ""),
            roman_for_preface=strtobool(form.get("roman_for_preface", "false")),
            temp_dir=context.temp_dir,
            logs_dir=logs_dir,
            bookmark_setting=form.get("bookmark_setting", "tab-title"),
        )
    )


def _get_coversheet_file(request_files: dict[str, FileStorage]) -> FileStorage | None:
    """Gets the coversheet FileStorage object from the request if it exists."""
    if "coversheet" in request_files and request_files["coversheet"].filename != "":
        current_app.logger.debug("Coversheet found in form submission")
        return request_files["coversheet"]
    return None


def _handle_csv_index_upload(request_files: dict[str, FileStorage]):
    """Handles CSV index upload and returns its content as a string."""
    if "csv_index" in request_files and request_files["csv_index"].filename:
        csv_file = request_files["csv_index"]
        try:
            # Read the content of the file stream directly into a string
            csv_content = csv_file.stream.read().decode("utf-8")
        except Exception as e:
            msg = f"Could not read uploaded CSV index: {e}"
            current_app.logger.exception(msg)  # Use .exception for logging with traceback
            # We return a tuple (error_response, None) to be handled by the caller
            return jsonify({"status": "error", "message": msg}), 400, None
        return None, None, csv_content

    return None, None, None


def _build_and_respond(received_output_file, zip_file_path, session_id):
    """Validates bundle artifacts, copies them to the final directory, and creates a success response."""
    bundles_dir = Path(tempfile.gettempdir()) / "buntool" / "bundles"

    if not (received_output_file and Path(received_output_file).exists()):
        msg = f"Error preparing PDF file for download. Session code: {session_id}"
        current_app.logger.error(f"PDF file not found at: {received_output_file}")
        return jsonify({"status": "error", "message": msg}), 500

    final_output_path = bundles_dir / Path(received_output_file).name
    shutil.copy2(received_output_file, final_output_path)
    current_app.logger.debug(f"Copied final PDF to: {final_output_path}")

    final_zip_path_str = None
    zip_path = Path(zip_file_path)
    if zip_file_path and zip_path.exists():
        final_zip_path = bundles_dir / zip_path.name
        shutil.copy2(zip_file_path, final_zip_path)
        final_zip_path_str = str(final_zip_path)
        current_app.logger.debug(f"Copied final ZIP to: {final_zip_path}")
    else:
        current_app.logger.warning(f"ZIP file not found at: {zip_file_path}. Continuing without zip.")

    return jsonify(
        {"status": "success", "message": "Bundle created successfully!", "bundle_path": str(final_output_path), "zip_path": final_zip_path_str}
    )


# @app.route('/')
# def index():
#     return render_template('index.html')


# @app.route('/create_bundle', methods=['GET', 'POST'])
def create_bundle():
    if request.method == "GET":
        return render_template("index.html")

    t1 = datetime.now()
    timestamp = t1.strftime("%Y%m%d_%H%M%S")
    session_id = str(uuid.uuid4())[:8]
    user_agent = request.headers.get("User-Agent") or ""
    current_app.logger.debug("******************APP HEARS A CALL******************")
    current_app.logger.debug(f"New session ID: {session_id} {user_agent}")

    if "files" not in request.files:
        current_app.logger.error("Cannot create bundle: No files found in form submission")
        return jsonify({"status": "error", "message": "No files found. Please add files and try again."}), 400

    logs_dir = Path(tempfile.gettempdir()) / "logs" if is_running_in_lambda() else Path("logs")

    session_file_handler = None
    try:
        base_dir = tempfile.gettempdir() if is_running_in_lambda() else "."
        temp_dir = Path(base_dir) / "tempfiles" / session_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        current_app.logger.debug(f"Temporary directory created: {temp_dir}")

        logs_path = logs_dir / f"buntool_{session_id}.log"
        session_file_handler = logging.FileHandler(logs_path)
        # Use a standard formatter for the file log
        file_formatter = logging.Formatter("%(asctime)s-%(levelname)s-[APP]: %(message)s")
        session_file_handler.setLevel(logging.DEBUG)
        session_file_handler.setFormatter(file_formatter)
        current_app.logger.addHandler(session_file_handler)

        context = RequestContext(session_id=session_id, user_agent=user_agent, timestamp=timestamp, temp_dir=temp_dir)

        bundle_config = _get_bundle_config_from_form(request.form, context, logs_dir)
        output_file = get_output_filename(
            bundle_config.case_details["bundle_title"], bundle_config.case_details["case_name"], timestamp, bundle_config.footer_prefix or "Bundle"
        )
        current_app.logger.debug(f"generated output filename: {output_file}")

        files = request.files.getlist("files")
        total_size = sum(f.content_length for f in files if f.content_length is not None)
        if total_size > current_app.config["MAX_CONTENT_LENGTH"]:
            msg = f"Total size of files exceeds maximum allowed size: {total_size} > {current_app.config['MAX_CONTENT_LENGTH']}"
            current_app.logger.error(msg)
            return jsonify({"status": "error", "message": msg}), 400

        coversheet_file = _get_coversheet_file(request.files)

        error_response, status_code, csv_content_string = _handle_csv_index_upload(request.files)
        if error_response:
            # If status_code is None, default to 400
            return error_response if status_code is None else (error_response, status_code)

        bundle_config.csv_string = csv_content_string or ""
        log_msg = f"""
            Calling buntool.create_bundle with params:
            ....input_files: {[f.filename for f in files]}
            ....output_file: {output_file}
            ....coversheet_file: {coversheet_file.filename if coversheet_file else "None"}
            ....bundle_config elements: {bundle_config.__dict__}"""
        current_app.logger.info(textwrap.dedent(log_msg))

        # tm = TraceMalloc(current_app.logger)
        received_output_file, zip_file_path = bundle.create_bundle(files, output_file, coversheet_file, None, bundle_config)
        # tm.log()

        t2 = datetime.now()

        delta = t2 - t1
        current_app.logger.info(f"Bundle creation completed in {delta} for session ID: {session_id}")

        return _build_and_respond(received_output_file, zip_file_path, session_id)

    except Exception:
        current_app.logger.exception("Fatal Error in processing bundle")
        return jsonify({"status": "error", "message": f"Fatal error in creating bundle. Session code: {session_id}"}), 500

    finally:
        if session_file_handler and session_file_handler in current_app.logger.handlers:
            # This is crucial to release file handles and allow garbage collection
            session_file_handler.close()
            current_app.logger.removeHandler(session_file_handler)


# @app.route('/download/bundle', methods=['GET'])
def download_bundle():
    bundle_path = request.args.get("path")
    if not bundle_path:
        return jsonify({"status": "error", "message": "Download Error: Bundle download path could not be found."}), 400

    absolute_path = Path(bundle_path).resolve()
    if not absolute_path.exists():
        return jsonify({"status": "error", "message": "Download Error: bundle does not exist in expected location."}), 404

    return send_file(absolute_path, as_attachment=True)


# @app.route('/download/zip', methods=['GET'])
def download_zip():
    zip_path = request.args.get("path")
    if not zip_path:
        return jsonify({"status": "error", "message": "Download Error: Zip download path could not be found."}), 400

    absolute_path = Path(zip_path).resolve()
    if not absolute_path.exists():
        return jsonify({"status": "error", "message": "Download Error: zip does not exist in expected location."}), 404

    return send_file(absolute_path, as_attachment=True)


def create_app():
    """Entry point for running the Flask application."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # file size limit in MB
    app.logger.setLevel(logging.DEBUG)
    app.logger.propagate = False  # Prevent duplicate logging if root logger also has handlers

    # Apply color formatter to the default console handler
    for handler in app.logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            formatter = ColoredFormatter(
                "%(log_color)s%(asctime)s - %(levelname)s - [APP]: %(message)s",
                log_colors={"DEBUG": "cyan", "INFO": "green", "WARNING": "yellow", "ERROR": "red", "CRITICAL": "red,bg_white"},
                reset=True,
            )
            handler.setFormatter(formatter)

    logs_dir = Path(tempfile.gettempdir()) / "logs" if is_running_in_lambda() else Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    bundles_dir = Path(tempfile.gettempdir()) / "buntool" / "bundles"
    bundles_dir.mkdir(parents=True, exist_ok=True)

    if os.environ.get("BUNTOOL_DEV") and LiveReload:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.jinja_env.auto_reload = True
        LiveReload(app)
        app.logger.info("LiveReload enabled")

    with app.app_context():
        # Import and register routes within the app context
        @app.route("/")
        def index():
            return render_template("index.html")

        # Register other routes
        app.add_url_rule("/create_bundle", view_func=create_bundle, methods=["GET", "POST"])
        app.add_url_rule("/download/bundle", view_func=download_bundle, methods=["GET"])
        app.add_url_rule("/download/zip", view_func=download_zip, methods=["GET"])

        # Replace all direct `app.logger` calls with `current_app.logger` or pass logger around

    # s3 = boto3.client('s3')
    # bucket_name = os.environ.get('s3_bucket', 'your-default-bucket')
    return app


def main():
    """Creates and runs the Flask application."""
    created_app = create_app()
    host = os.environ.get("BUNTOOL_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("BUNTOOL_PORT", "7001"))

    created_app.logger.info("buntool starting...")

    if os.environ.get("BUNTOOL_DEV"):
        if LiveReload is None:
            created_app.logger.warning("BUNTOOL_DEV is set but flask-livereload is not installed. Live reload will not work.")
        created_app.logger.info(f"APP - Starting in DEVELOPMENT mode on {host}:{port}")
        created_app.run(host=host, port=port, debug=True)  # nosec B201
    else:
        created_app.logger.info(f"APP - Server started on {host}:{port} (Production/Waitress).")
        serve(created_app, host=host, port=port, threads=4, connection_limit=100, channel_timeout=120)


if __name__ == "__main__":
    main()
