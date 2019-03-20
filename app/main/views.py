import os
import json
import re

from flask import render_template, session, redirect, url_for, abort, flash, \
    request, current_app, Response, send_from_directory

from sqlalchemy.sql.expression import func

from . import main
from .. import db
from ..models import FormField, Document, Page, TextLine, TaggedText, TextLineSource, Form


def get_class_by_tablename(tablename):
  """Return class reference mapped to table.

  :param tablename: String with name of table.
  :return: Class reference or None.
  """
  for c in db.Model._decl_class_registry.values():
      if hasattr(c, '__tablename__') and c.__tablename__ == tablename:
          return c



@main.route('/', methods=['GET', 'POST'])
def index():
    # page = request.args.get('page', 1, type=int)
    return render_template('index.html')


@main.route('/tag-document/<string:filename>/<int:page_number>', methods=['GET', 'POST'])
def tag_document(filename, page_number):
    scaling_factor = 1.5
    doc = Document.query.filter_by(filename=filename).first_or_404()
    page = doc.pages.filter_by(page_number=page_number).first_or_404()
    # form_number = 'Form 366' if page.is_start_page else 'Form 366A'
    # form_number = page.form_number
    # form_options = [f[0] for f in db.session.query(FormField.form_number).distinct().all()]
    # form_options = sorted(set(form_options) - set([form_number])) + ['Other']
    # fields = FormField.query.filter_by(form_number=form_number).all()
    # total_field_count = len(fields)
    # fields = [{'id': field.id, 'name': field.name} for field in fields]
    
    # First get page dimensions and text area positions
    # Get page dimensions to scale the text positions
    x_min_page, y_min_page, x_max_page, y_max_page = page.x_min, page.y_min, page.x_max, page.y_max
    x_min_page *= scaling_factor
    y_min_page *= scaling_factor
    x_max_page *= scaling_factor
    y_max_page *= scaling_factor
    page_width = x_max_page - x_min_page
    page_height = y_max_page - y_min_page
    lines = [(
              line.id,
              scaling_factor * (line.x_min - x_min_page), # left
              y_max_page - (scaling_factor * line.y_max), # top
              scaling_factor * (line.y_max - line.y_min), # height
              scaling_factor * (line.x_max - line.x_min), # width
              re.sub('\n', '<br>', line.text) # text
             ) for line in page.text_lines.all()
            ]
    
    # Now we check what the progess is for the page: which fields are tagged vs all fields
    # This is a hack, since I couldn't figure out how to build the query in 
    # the sqlalchemy ORM.
    # tagged_lines = [line.tagged_text.all() for line in page.text_lines]
    # tagged_lines = [item for sublist in tagged_lines for item in sublist]

    # completed_fields = [{'id': line.field_id, 'name': line.field.name} for line in tagged_lines] if tagged_lines is not None else []
    # completed_field_ids = [f['id'] for f in completed_fields]
    # missing_fields = [f for f in fields if f['id'] not in completed_field_ids]
    # return render_template('ler_page.html', filename=filename, page=page_number, 
    #                        lines=lines, page_height=page_height, page_width=page_width,
    #                        fields=json.dumps(fields), form_number=form_number,
    #                        completed_fields=json.dumps(completed_fields),
    #                        missing_fields = json.dumps(missing_fields),
    #                        total_field_count=total_field_count,
    #                        form_options=form_options)
    return render_template('tag_page.html', filename=filename, page=page_number, 
                           lines=lines, page_height=page_height, page_width=page_width)

@main.route('/document-thumbs/<filename>', methods=['GET', 'POST'])
def document_thumbs(filename):
    doc_count = Document.query.filter_by(is_target_doc=True).count()
    doc = Document.query.filter_by(filename=filename).first_or_404()
    if doc.pages.first() is None: # File not loaded, load file
        Document.load_pdf(doc.filename)
    if doc.pages.first() is None:
        flash('You have no more LERs to find start pages for.')
        return redirect(url_for('main.index'))

    page_count = doc.page_count
    return render_template('document_thumbs.html', filename=filename, page_count=page_count,
    pages=doc.pages, progress=None)


@main.route('/ler-thumbs/<filename>', methods=['GET', 'POST'])
def ler_thumbs(filename):
    doc_count = Document.query.filter_by(is_target_doc=True).count()
    # has_start_page = Page.query.filter_by(is_start_page=True).distinct().count()
    has_form = Page.query.filter_by()
    # progress = str(round(100 * has_start_page / doc_count))
    progress = str(round(100 * 0))
    doc = Document.query.filter_by(filename=filename).first_or_404()
    if doc.pages.first() is None: # File not loaded, load file
        Document.load_pdf(doc.filename)
    if doc.pages.first() is None:
        flash('You have no more LERs to find start pages for.')
        return redirect(url_for('main.index'))

    page_count = doc.page_count
    return render_template('ler_thumbs.html', filename=filename, page_count=page_count,
    pages=doc.pages, progress=progress)


@main.route('/image/<filename>/<page>', methods=['GET'])
def get_pages(filename, page):
    return send_from_directory(current_app.config['PDF_IMAGE_DIRECTORY'],
                               filename='{}-{}.png'.format(filename, page))


@main.route('/image/<filename>', methods=['GET'])
def get_single_page(filename):
    return send_from_directory(current_app.config['PDF_IMAGE_DIRECTORY'],
                               filename='{}.png'.format(filename))


@main.route('/randomLERTagStart')
def random_ler_tag_start():
    filename = db.engine.execute(('SELECT filename FROM documents '
                                            'WHERE id NOT IN ('
                                                'SELECT DISTINCT doc_id FROM pages '
                                                    'WHERE is_start_page=true) '
                                            'AND is_target_doc=True '
                                            'ORDER BY RANDOM() '
                                            'LIMIT 1;')).first()
    if filename:
        filename = filename[0]
        return redirect(url_for('main.ler_thumbs', filename=filename))
    
    flash('You have no more LERs to find start pages for.')
    return redirect(url_for('main.index'))


@main.route('/randomDocument/<string:form_id>')
def random_document():
    # filename = db.engine.execute(('SELECT filename FROM documents '
    #                                         'WHERE id NOT IN ('
    #                                             'SELECT DISTINCT doc_id FROM pages '
    #                                                 'WHERE is_start_page=true) '
    #                                         'AND is_target_doc=True '
    #                                         'ORDER BY RANDOM() '
    #                                         'LIMIT 1;')).first()
    filename = Document.query.filter_by(form_id).order_by(func.random()).first()
    if filename:
        filename = filename[0]
        return redirect(url_for('main.ler_thumbs', filename=filename))
    
    flash('You have no more LERs to find start pages for.')
    return redirect(url_for('main.index'))


@main.route('/randomler')
def random_ler():
    filename = db.engine.execute(('SELECT filename FROM documents '
                                            'ORDER BY RANDOM() '
                                            'LIMIT 1;')).first()
    if filename:
        filename = filename[0]
        return redirect(url_for('main.ler_thumbs', filename=filename))
    abort(404)


@main.route('/lertest/<string:filename>/<int:page_number>', methods=['GET'])
def ler_test(filename, page_number):
    scaling_factor = 1.5
    doc = Document.query.filter_by(filename=filename).first_or_404()
    page = doc.pages.filter_by(page_number=page_number).first_or_404()
    # form_number = 'Form 366' if page.is_start_page else 'Form 366A'
    form_number = page.form_number
    form_options = [f[0] for f in db.session.query(FormField.form_number).distinct().all()]
    form_options = sorted(set(form_options) - set([form_number])) + ['Other']
    fields = FormField.query.filter_by(form_number=form_number).all()
    total_field_count = len(fields)
    fields = [{'id': field.id, 'name': field.name} for field in fields]
    
    # First get page dimensions and text area positions
    # Get page dimensions to scale the text positions
    x_min_page, y_min_page, x_max_page, y_max_page = page.x_min, page.y_min, page.x_max, page.y_max
    x_min_page *= scaling_factor
    y_min_page *= scaling_factor
    x_max_page *= scaling_factor
    y_max_page *= scaling_factor
    page_width = x_max_page - x_min_page
    page_height = y_max_page - y_min_page
    lines = [(
              line.id,
              scaling_factor * (line.x_min - x_min_page), # left
              y_max_page - (scaling_factor * line.y_max), # top
              scaling_factor * (line.y_max - line.y_min), # height
              scaling_factor * (line.x_max - line.x_min), # width
              re.sub('\n', '<br>', line.text) # text
             ) for line in page.text_lines.all()
            ]
    
    # Now we check what the progess is for the page: which fields are tagged vs all fields
    # This is a hack, since I couldn't figure out how to build the query in 
    # the sqlalchemy ORM.
    tagged_lines = [line.tagged_text.all() for line in page.text_lines]
    tagged_lines = [item for sublist in tagged_lines for item in sublist]

    completed_fields = [{'id': line.field_id, 'name': line.field.name} for line in tagged_lines] if tagged_lines is not None else []
    completed_field_ids = [f['id'] for f in completed_fields]
    missing_fields = [f for f in fields if f['id'] not in completed_field_ids]
    return render_template('ler_test.html', filename=filename, page=page_number, 
                           lines=lines, page_height=page_height, page_width=page_width,
                           fields=json.dumps(fields), form_number=form_number,
                           completed_fields=json.dumps(completed_fields),
                           missing_fields = json.dumps(missing_fields),
                           total_field_count=total_field_count,
                           form_options=form_options)


@main.route('/table/<string:tablename>')
def view_table(tablename):
    page = request.args.get('page', 1, type=int)
    table = get_class_by_tablename(tablename)
    if table is None:
        abort(404)
    columns = table.metadata.tables[tablename].columns.keys()
    pagination = table.query.order_by(table.id.asc()).paginate(page,
                        per_page=current_app.config['TABLE_ITEMS_PER_PAGE'],
                        error_out=False)
    items = pagination.items
    return render_template('table.html', columns=columns,
                           items=items, pagination=pagination,
                           tablename=tablename)


@main.route('/page')
def page():
    filename = 'ML15009A030'
    form_id = 1
    form_id = 1
    page_number = 1
    doc = Document.query.filter_by(filename=filename).first_or_404()
    page = doc.pages.filter_by(page_number=page_number).first_or_404()
    form_types = Form.query.all()
    # First get page dimensions and text area positions
    # Get page dimensions to scale the text positions
    x_min_page, y_min_page, x_max_page, y_max_page = page.x_min, page.y_min, page.x_max, page.y_max
    page_width = x_max_page - x_min_page
    page_height = y_max_page - y_min_page
    lines = [(
              line.id,
              line.x_min - x_min_page, # left
              y_max_page - line.y_max, # top
              line.y_max - line.y_min, # height
              line.x_max - line.x_min, # width
              re.sub('\n', '<br>', line.text) # text
             ) for line in page.text_lines.all()
            ]
    return render_template('page.html', filename=filename, page=page_number, 
                           lines=lines, page_height=page_height, page_width=page_width,
                           form_id=form_id, form_types=form_types)