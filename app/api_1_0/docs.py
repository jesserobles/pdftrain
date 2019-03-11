from flask import jsonify, request, g, abort, url_for, current_app
from .. import db
from ..models import FormField, Form, Document, Page, TextLine, TaggedText, Permission, \
    MissingField, TextLineSource
from . import api
# from .decorators import permission_required
from .errors import forbidden

@api.route('/', methods=['GET'])
def api_home():
    return jsonify({
        'status': 'WORKING'
    })


@api.route('/notTargetDoc', methods=['PUT'])
def not_target_doc():
    """API function to update the Document's is_target_doc to False,
       which indicates that we are not interested in this document.
    """
    data = request.json
    filename = data['filename']
    doc = Document.query.filter_by(filename=filename).first_or_404()
    doc.is_target_doc = False
    db.session.add(doc)
    db.session.commit()
    return jsonify({
        'filename': filename
    })


@api.route('/addPageFormTag', methods=['PUT'])
def add_page_form_tag():
    """API function to associate a page with a form.
       This takes a JS object with pageID and formID,
       and adds the Form to the Page object.
    """
    data = request.json
    page_id = int(data['pageID'])
    form_id = int(data['formID'])
    page = Page.query.filter_by(id=page_id).first_or_404()
    form = Form.query.filter_by(id=form_id).first_or_404()
    page.page_form = form
    db.session.commit()
    return jsonify({
        'PageId': page_id,
        'FormId': form_id
    })


@api.route('/addTaggedText', methods=['POST'])
def add_tagged_text():
    """API function to add a TaggedText object to the database.
       This takes a JS object with lineID and fieldID, looks
       up the TextLine and FormField objects, and adds the 
       TaggedText object.
    """
    data = request.json
    # Line ID, Field ID
    line_id = int(data['lineID'])
    field_id = int(data['fieldID'])
    line = TextLine.query.filter_by(id=line_id).first_or_404()
    field = FormField.query.filter_by(id=field_id).first_or_404()
    tagged_text = TaggedText(textline=line, field=field)
    db.session.add(tagged_text)
    db.session.commit()
    return jsonify(tagged_text.to_json())


@api.route('/pageTagProgress/<int:page_id>', methods=['GET'])
def page_tag_progress(page_id):
    """API function to get tag progress for a page. It takes
       a JS object with pageID, and returns a JS object with
       CompletedFields, MissingFields,
       IncompleteFields, and TotalFieldCounts.
    """
    data = request.json
    page_id = int(page_id)
    page = Page.query.filter_by(id=page_id).first_or_404()
    form = page.page_form
    total_field_count = form.form_fields.count()
    all_fields = form.form_fields.all()
    completed_fields = [field.field for field in TaggedText.query.join(TextLine).join(Page)\
                        .filter(Page.id == page.id)]
    missing_fields = [field.field for field in page.missing_fields]
    ids = set([item.id for item in completed_fields] + [m.id for m in missing_fields])
    incomplete_fields = [field for field in all_fields if field.id not in ids]

    return jsonify({
        'CompletedFields': [cf.to_json() for cf in completed_fields], 
        'MissingFields': [mf.to_json() for mf in missing_fields],
        'IncompleteFields': [ic.to_json() for ic in incomplete_fields],
        'TotalFieldCounts': total_field_count
    })


# TODO - create api route for adding a TextLine, TaggedText for CropJS
@api.route('/addTextLine', methods=['POST'])
def add_text_line():
    """API function to add a new TextLine based off of CropJS object
       selections. It takes a JS object with pageID, x_min, y_min, 
       x_max, y_max, and field_id. Adds a TextLine and source_id = 2,
       and associated TaggedText
    """
    source = TextLineSource.query.filter_by(name='User').first()
    data = request.json
    page_id = int(data['pageID'])
    x_min = float(data['x_min'])
    y_min = float(data['y_min'])
    x_max = float(data['x_max'])
    y_max = float(data['y_max'])
    field_id = int(data['field_id'])
    text_line = TextLine(page_id=page_id, text='', x_min=x_min, y_min=y_min,
                         x_max=x_max, y_max=y_max, textline_source=source)
    db.session.add(text_line)
    tagged_text = TaggedText(textline=text_line, field_id=field_id)
    db.session.add(tagged_text)
    db.session.commit()
    return jsonify(tagged_text.to_json())


@api.route('/getFieldNames/<int:form_id>')
def get_field_names(form_id):
    form = Form.query.filter_by(id=form_id).first_or_404()
    fields = [field.to_json() for field in form.form_fields]
    return jsonify(fields)
# @api.route('/addStartPage/<filename>/<page_number>', methods=['GET'])
# def add_start_page(filename, page_number):
#     doc = Document.query.filter_by(filename=filename).first_or_404()
#     page = doc.pages.filter_by(page_number=page_number).first_or_404()
#     page.is_start_page = True
#     db.session.add(page)
#     return jsonify({
#         'filename': filename,
#         'start_page': page.page_number
#     })


# @api.route('/addstartpages', methods=['PUT'])
# def add_start_pages():
#     data = request.json
#     filename = data['filename']
#     start_pages = [int(page) for page in data['start_pages']]
#     doc = Document.query.filter_by(filename=filename).first_or_404()
#     for page in doc.pages:
#         page.is_start_page = True if page.page_number in start_pages else False
#         db.session.add(page)
#     return jsonify({
#         'filename': filename,
#         'start_pages': start_pages
#     })


# @api.route('/notler', methods=['PUT'])
# def not_ler():
#     data = request.json
#     filename = data['filename']
#     doc = Document.query.filter_by(filename=filename).first_or_404()
#     doc.is_ler = False
#     db.session.add(doc)
#     return jsonify({
#         'filename': filename
#     })

# @api.route('/getStartTagStatus', methods=['GET'])
# def get_start_tag_status():
#     doc_count = Document.query.filter_by(is_ler=True).count()
#     has_start_page = Page.query.filter_by(is_start_page=True).distinct().count()
#     return jsonify({
#         'tagged_document_count': has_start_page,
#         'total_document_count': doc_count
#     })

