from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
import os
# import sys
import bundle as buntool
import shutil
import logging
from datetime import datetime
import uuid
from waitress import serve
import csv
#import boto3

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # file size limit in MB
app.logger.setLevel(logging.DEBUG)

# s3 = boto3.client('s3')
# bucket_name = os.environ.get('s3_bucket', 'your-default-bucket')


# def upload_to_s3(file_path, s3_key):
#     s3.upload_file(file_path, bucket_name, s3_key)
#     return f"s3://{bucket_name}/{s3_key}"


def is_running_in_lambda():
    return 'AWS_LAMBDA_FUNCTION_NAME' in os.environ  # seems to work?


if is_running_in_lambda():
    logs_dir = '/tmp/logs'
else:
    logs_dir = os.path.join('logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Configure logging
# # Configure upload folder and bundles output folder
# UPLOAD_FOLDER = 'uploads'
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)

BUNDLES_DIR = '/tmp/bundles'
if not os.path.exists(BUNDLES_DIR):
    os.makedirs(BUNDLES_DIR)


def save_uploaded_file(file, directory, filename=None):
    # Takes in a file object, the tmpfiles directory path, and an optional filename.
    # passes the filename (supplied, or original) through secure_filename.
    # creates a filepath by joining the tmp directory and filename.
    # saves the file to the filepath
    # returns the filepath if successful, None if not.
    if file and file.filename:
        filename = secure_filename(filename) or secure_filename(file.filename)
        filepath = os.path.join(directory, filename)
        file.save(filepath)
        app.logger.debug(f"Saved file: {filepath}")
        return filepath
    return None


def strtobool(value: str) -> bool:
    value = value.lower()
    if value in ("y", "yes", "on", "1", "true", "t", "True", "enabled"):
        return True
    return False


def get_output_filename(bundle_title, case_name, timestamp, fallback="Bundle"):
    # Takes in the bundle title, case name, and a timestamp.
    # purpose is to guard against extra-long filenames.
    # Returns the output filename picked among many fallback options.
    output_file = f"{bundle_title}_{case_name}_{timestamp}.pdf"
    if len(output_file) > 100:
        # take first 20 chars of bundle title and add case name:
        output_file = f"{bundle_title[:20]}_{case_name}_{timestamp}.pdf"
    if len(output_file) > 100:
        # take first 20 chars of bundle title, first 20 chars of case name, and add timestamp:
        output_file = f"{bundle_title[:30]}_{case_name[:30]}_{timestamp}.pdf"
    if len(output_file) > 100:
        # this should never happen:
        output_file = f"{fallback}_{timestamp}.pdf"
    if len(output_file) > 100:
        # this should doubly never happen:
        output_file = f"{timestamp}.pdf"
    return output_file


def synchronise_csv_index(uploaded_csv_path, filename_mappings):
    # takes the path of the uploaded csv file and a dictionary of filename mappings (due to sanitising filenames of uploads).
    # creates a new csv file with the same structure as the original, but with the filenames replaced with secure versions.
    # returns the path of the new csv file.
    sanitised_filenames_csv_path = uploaded_csv_path.replace('index_', 'securefilenames_index_')
    app.logger.info(f"secure_csv_path: {sanitised_filenames_csv_path}")
    try:
        with open(uploaded_csv_path, 'r', newline='', encoding='utf-8') as infile:
            with open(sanitised_filenames_csv_path, 'w', newline='', encoding='utf-8') as outfile:
                reader = csv.reader(infile)
                writer = csv.writer(outfile)
                # print content of input csv:
                app.logger.debug(f"Reading input CSV:")
                # try:
                #     header = next(reader)
                #     app.logger.debug(f"[APP]-- Read header: {header}")
                #     writer.writerow(header)
                #     app.logger.debug(f"[APP]-- Wrote header")
                # except StopIteration:
                #     app.logger.error("[APP]-- CSV file is empty!")
                #     return

                for row in reader:
                    app.logger.debug(f"Processing row: {row}")
                    try:
                        if row[0] == 'Filename' and row[2] == 'Page':
                            app.logger.debug(f"..Found header row")
                            writer.writerow(row)
                            continue
                        if len(row) > 3 and row[3] == '1':
                            app.logger.debug(f"..Found section marker row")
                            writer.writerow(row)
                            continue

                        original_upload_filename = row[0]
                        secure_name = filename_mappings.get(original_upload_filename)
                        if secure_name is None:
                            secure_name = secure_filename(original_upload_filename)

                        row[0] = secure_name
                        writer.writerow(row)
                        app.logger.debug(f"..Wrote processed file row: {row}")
                    except Exception as e:
                        app.logger.error(f"..Error processing row {row}: {str(e)}")
                        raise

    except Exception as e:
        app.logger.error(f"..Error in save_csv_index: {str(e)}")
        raise

    app.logger.info(f"..saved csv index as {sanitised_filenames_csv_path}")
    return sanitised_filenames_csv_path


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/create_bundle', methods=['GET', 'POST'])
def create_bundle():
    if request.method == 'GET':
        return render_template('index.html')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_id = str(uuid.uuid4())[:8]
    user_agent = request.headers.get('User-Agent')
    app.logger.debug(f"******************APP HEARS A CALL******************")
    app.logger.debug(f"New session ID: {session_id} {user_agent}")
    # check if csv has been passed:

    # check whether input files are actually povided:
    if 'files' not in request.files:
        app.logger.error(f"Cannot create bundle: No files found in form submission")
        return jsonify({"status": "error", "message": "No files found. Please add files and try again."})

    try:
        # Create temporary working directory in /tmp/tempfiles/{session_id}:
        if is_running_in_lambda():
            temp_dir = os.path.join('/tmp', 'tempfiles', session_id)
            if not os.path.exists('/tmp/tempfiles'):
                os.makedirs('/tmp/tempfiles')
        else:
            temp_dir = os.path.join('tempfiles', session_id)
            if not os.path.exists('tempfiles'):
                os.makedirs('tempfiles')
        os.makedirs(temp_dir)
        app.logger.debug(f"Temporary directory created: {temp_dir}")

        # Add FileHandler for session-specific logging
        logs_path = os.path.join(logs_dir, f'buntool_{session_id}.log')
        session_file_handler = logging.FileHandler(logs_path)
        session_file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s-%(levelname)s-[APP]: %(message)s')
        session_file_handler.setFormatter(formatter)
        app.logger.addHandler(session_file_handler)

        # Get form data
        # Ingest csv index
        app.logger.debug(f"Ingesting form information...")
        if request.files.get('csv_index'):
            app.logger.info(f"..index file found in form submission")
            app.logger.info(f"..index data: {request.files.get('csv_index')}")
        else:
            app.logger.info(f"..No CSV index found.")

        # ingest other form data:
        bundle_title = request.form.get('bundle_title', 'Bundle') if request.form.get('bundle_title') else 'Bundle'
        case_name = request.form.get('case_name')
        claim_no = request.form.get('claim_no')
        page_num_align = request.form.get('page_num_align')
        footer_font = request.form.get('footer_font')
        index_font = request.form.get('index_font')
        page_num_style = request.form.get('page_num_style')
        footer_prefix = request.form.get('footer_prefix')
        confidential_bool = request.form.get('confidential_bool')
        date_setting = request.form.get('date_setting')
        roman_for_preface = bool(strtobool(request.form.get('roman_for_preface')))
        case_details = [bundle_title, claim_no, case_name]
        zip_bool = True  # option not implemented for GUI control.
        bookmark_setting = request.form.get('bookmark_setting')

        output_file = get_output_filename(bundle_title, case_name, timestamp, footer_prefix)
        app.logger.debug(f"generated output filename: {output_file}")

        # Save uploaded files
        app.logger.debug(f"Gathering uploaded files...")
        files = request.files.getlist('files')
        # check whether files exceed max allowed overall size of MAX_CONTENT_LENGTH:
        total_size = sum([f.content_length for f in files])
        if total_size > app.config['MAX_CONTENT_LENGTH']:
            app.logger.error(
                f"Total size of files exceeds maximum allowed size: {total_size} > {app.config['MAX_CONTENT_LENGTH']}")
            return jsonify({"status": "error",
                            "message": f"Total size of files exceeds maximum allowed size: {total_size} > {app.config['MAX_CONTENT_LENGTH']}"})
        app.logger.debug(f"....{files}")
        input_files = []
        filename_mappings = {}
        for file in files:
            app.logger.debug(f"..Processing {file.filename}")
            if file.filename:
                secure_name = secure_filename(file.filename)
                filename_mappings[file.filename] = secure_name
                # app.logger.debug(f"[{session_id}-{timestamp}-APP]--filename_mappings: {filename_mappings}")
                filepath = save_uploaded_file(file, temp_dir, secure_name)
                if filepath:
                    input_files.append(filepath)
            else:
                app.logger.error(f"..No filename found for {file}")
            if not os.path.exists(filepath):
                app.logger.error(f"File not found at: {filepath}")
            else:
                app.logger.info(f"..File saved to: {filepath}")

        # Save coversheet if provided
        secure_coversheet_filename = None
        if 'coversheet' in request.files and request.files['coversheet'].filename != '':
            app.logger.debug(f"Coversheet found in form submission")
            cover_file = request.files['coversheet']
            # if cover_file and cover_file.filename:
            # Generate a secure and unique filename for coversheet
            secure_coversheet_filename = secure_filename(f'coversheet_{session_id}_{timestamp}.pdf')
            coversheet_filepath = save_uploaded_file(cover_file, temp_dir, secure_coversheet_filename)
            app.logger.debug(f"Coversheet path: {coversheet_filepath}")
        else:
            app.logger.debug(f"No coversheet found in form submission")

        # Save CSV index
        saved_csv_path = ""
        if 'csv_index' in request.files:
            app.logger.debug(f"CSV index found in form submission: {request.files['csv_index']}")
            csv_file = request.files['csv_index']
            if csv_file and csv_file.filename:
                secure_csv_filename = secure_filename(f'index_{session_id}_{timestamp}.csv')
                saved_csv_path = save_uploaded_file(csv_file, temp_dir, secure_csv_filename)
                # if secure_csv_path:
                # permanent_csv_path = os.path.join(temp_dir, secure_csv_filename)
                sanitised_filenames_index_csv = synchronise_csv_index(saved_csv_path, filename_mappings)
        else:
            app.logger.debug(f"No CSV index found in form submission")
            sanitised_filenames_index_csv = None
        if not os.path.exists(saved_csv_path):
            app.logger.error(f"CSV file not found at: {saved_csv_path}")
            return jsonify(
                {"status": "error", "message": f"Index data did not upload correctly. Session code: {session_id}"}), 400
        else:
            app.logger.debug(f"CSV saved to: {saved_csv_path}")

        # Create bundle - main function call
        try:
            app.logger.info(f"Calling buntool.create_bundle with params:")
            app.logger.info(f"....input_files: {input_files}")
            app.logger.info(f"....output_file: {output_file}")
            app.logger.info(f"....secure_coversheet_filename: {secure_coversheet_filename}")
            app.logger.info(f"....sanitised_filenames_index_csv: {sanitised_filenames_index_csv}")
            app.logger.info(f"....bundle_config elements:")
            app.logger.info(f"........timestamp: {timestamp}")
            app.logger.info(f"........case_details: {case_details}")
            app.logger.info(f"........confidential_bool: {confidential_bool}")
            app.logger.info(f"........zip_bool: {zip_bool}")
            app.logger.info(f"........session_id: {session_id}")
            app.logger.info(f"........user_agent: {user_agent}")
            app.logger.info(f"........page_num_align: {page_num_align}")
            app.logger.info(f"........index_font: {index_font}")
            app.logger.info(f"........footer_font: {footer_font}")
            app.logger.info(f"........page_num_style: {page_num_style}")
            app.logger.info(f"........footer_prefix: {footer_prefix}")
            app.logger.info(f"........date_setting: {date_setting}")
            app.logger.info(f"........roman_for_preface: {roman_for_preface}")
            app.logger.info(f"........temp_dir: {temp_dir}")
            app.logger.info(f"........logs_dir: {logs_dir}")
            app.logger.info(f"........bookmark_setting: {bookmark_setting}")
            # Create BundleConfig instance
            bundle_config = buntool.BundleConfig(
                timestamp=timestamp,
                case_details=case_details,
                csv_string=None,
                confidential_bool=confidential_bool,
                zip_bool=zip_bool,
                session_id=session_id,
                user_agent=user_agent,
                page_num_align=page_num_align,
                index_font=index_font,
                footer_font=footer_font,
                page_num_style=page_num_style,
                footer_prefix=footer_prefix,
                date_setting=date_setting,
                roman_for_preface=roman_for_preface,
                temp_dir=temp_dir,
                logs_dir=logs_dir,
                bookmark_setting=bookmark_setting
            )

            received_output_file, zip_file_path = buntool.create_bundle(
                input_files,
                output_file,
                secure_coversheet_filename,
                sanitised_filenames_index_csv,
                bundle_config
            )

            # Copy both files to bundles folder
            if os.path.exists(received_output_file):
                final_output_path = os.path.join(BUNDLES_DIR, os.path.basename(received_output_file))
                shutil.copy2(received_output_file, final_output_path)
                app.logger.debug(f"Copied final PDF to: {final_output_path}")
            else:
                app.logger.error(f"PDF file not found at: {received_output_file}")
                return jsonify({"status": "error",
                                "message": f"Error preparing PDF file for download. Session code: {session_id}"}), 500

            if os.path.exists(zip_file_path):
                final_zip_path = os.path.join(BUNDLES_DIR, os.path.basename(zip_file_path))
                shutil.copy2(zip_file_path, final_zip_path)
                app.logger.debug(f"Copied final ZIP to: {final_zip_path}")
            else:
                app.logger.error(f"ZIP file not found at: {zip_file_path}")
                return jsonify(
                    {"status": "error", "message": f"Error creating ZIP archive. Session code: {session_id}"}), 500

            return jsonify({
                "status": "success",
                "message": "Bundle created successfully!",
                "bundle_path": final_output_path,
                "zip_path": final_zip_path
            })

        except Exception as e:
            app.logger.error(f"Fatal Error creating bundle: {str(e)}")
            return jsonify(
                {"status": "error", "message": "Fatal error creating bundle. Session code: {session_id}"}), 500

    except Exception as e:
        app.logger.error(f"Fatal Error in processing bundle: {str(e)}")
        return jsonify(
            {"status": "error", "message": f"Fatal error in creating bundle. Session code: {session_id}"}), 500

    finally:
        # Remove the session FileHandler to prevent duplicate logs
        if session_file_handler and session_file_handler in app.logger.handlers:
            app.logger.removeHandler(session_file_handler)

        # try:
        #     # Upload logs to s3:
        #     # As mentioned in the frontend, logs are always uploaded to s3, and the
        #     # only private info they contain are is user agent and index
        #     # data (basically, filenames and titles):
        #     logsurl = upload_to_s3(logs_path, f'logs/{os.path.basename(logs_path)}')
        #     # By contrast, the zip file has all the input files and the output bundle
        #     # itself. It almost certainly contains private data.
        #     # In the /dev/ instance it's uploaded to s3 for testing purposes
        #     # and regularly cleaned out.It is disabled in stable version by commenting
        #     # out the following lin, but is left uncommented here for tranparency:
        #     #upload_to_s3(final_zip_path, f'bundles/{os.path.basename(final_zip_path)}')
        #     app.logger.debug(f"Upload to s3 successful: {logsurl}")
        # except Exception as e:
        #     app.logger.error(f"Error uploading logs or zip to s3: {str(e)}")
        #     pass


@app.route('/download/bundle', methods=['GET'])
def download_bundle():
    bundle_path = request.args.get('path')
    if not bundle_path:
        return jsonify({"status": "error", "message": f"Download Error: Bundle download path could not be found."}), 400

    absolute_path = os.path.abspath(bundle_path)
    if not os.path.exists(absolute_path):
        return jsonify(
            {"status": "error", "message": f"Download Error: bundle does not exist in expected location."}), 404

    return send_file(absolute_path, as_attachment=True)


@app.route('/download/zip', methods=['GET'])
def download_zip():
    zip_path = request.args.get('path')
    if not zip_path:
        return jsonify({"status": "error", "message": f"Download Error: Zip download path could not be found."}), 400

    absolute_path = os.path.abspath(zip_path)
    if not os.path.exists(absolute_path):
        return jsonify({"status": "error", "message": f"Download Error: zip does not exist in expected location."}), 404

    return send_file(absolute_path, as_attachment=True)


if __name__ == '__main__':
    app.logger.debug(f"APP - Server started on port 7001 -- Hello.")
    serve(app, host='0.0.0.0', port=7001, threads=4, connection_limit=100, channel_timeout=120)