from datetime import datetime
import os
import csv
import hashlib

from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app, request, url_for
from flask_login import UserMixin, AnonymousUserMixin
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from markdown import markdown
import bleach
from . import db
from . import login_manager

from .pdf.pdf import PDF


class Permission:
    READ = 0x01
    WRITE = 0x02
    APPROVE = 0x04
    ADMINISTER = 0x80


class Form(db.Model):
    __tablename__ = 'forms'
    id = db.Column(db.Integer, primary_key=True)
    form_name = db.Column(db.String(64))
    pages = db.relationship('Page', backref='page_form', lazy='dynamic')
    form_fields = db.relationship('FormField', backref='field_form', lazy='dynamic')


    def __repr__(self):
        return '<Form %r, %r>' % (self.id, self.form_name)

    
    def to_json(self):
        json = {
            'id': self.id,
            'form_name': self.form_name,
            'pages': [page.id for page in self.pages],
            'form_fields': [ff.id for ff in self.form_fields]
        }

        return json


class FormField(db.Model):
    __tablename__ = 'formfields'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, index=True)
    form_id = db.Column(db.Integer, db.ForeignKey('forms.id'))
    tags = db.relationship('TaggedText', backref='field', lazy='dynamic')
    missing_fields = db.relationship('MissingField', backref='field', lazy='dynamic')


    def __repr__(self):
        return '<FormField %r>' % self.id
    

    def to_json(self):
        json = {
            'id': self.id,
            'name': self.name,
            'form_id': self.form_id,
            'tags': [t.id for t in self.tags],
            'missing_fields': [mf.id for mf in self.missing_fields]
        }

        return json


    @staticmethod
    def insert_fields():
        with open('data/formfields.csv', 'r') as file:
            reader = csv.reader(file)
            for r in reader:
                field_name, fnumber = r
                # Check Form exists, else add new Form
                form = Form.query.filter_by(form_name=fnumber).first()
                if form is None:
                    form = Form(form_name=fnumber)
                    db.session.add(form)
                field = FormField(name=field_name, field_form=form)
                db.session.add(field)


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, index=True)
    # title = db.Column(db.String)
    # date_added = db.Column(db.DateTime(), default=datetime.utcnow)
    # document_date = db.Column(db.DateTime(), default=datetime.utcnow)
    # size = db.Column(db.String)
    is_target_doc = db.Column(db.Boolean, default=True)
    is_complete = db.Column(db.Boolean, default=False)
    page_count = db.Column(db.Integer)
    pages = db.relationship('Page', backref='document', lazy='dynamic')
    

    def __repr__(self):
        return '<Document %r>' % self.filename


    def to_json(self):
        json = {
            'id': self.id,
            'filename': self.filename,
            'is_target_doc': self.is_target_doc,
            'is_complete': self.is_complete,
            'page_count': self.page_count,
            'pages': [page.id for page in self.pages]
        }

        return json


    @staticmethod
    def insert_documents():
        with open('data/documents.csv', 'r') as file:
            reader = csv.reader(file)
            for r in reader:
                # title_, ml, dateadded, docdate, size_, page_count = r
                ml = r[1]
                page_count = r[-1]
                # docdate = datetime.strptime(docdate, '%Y-%m-%d')
                # dateadded = datetime.strptime(dateadded, '%Y-%m-%d')
                # doc = Document(filename=ml, title=title_, date_added=dateadded, document_date=docdate, 
                #                size=size_, page_count=page_count)
                doc = Document(filename=ml, page_count=page_count)
                db.session.add(doc)


    @staticmethod
    def load_pdf(pdf_location):
        src_dir = current_app.config['PDF_FILE_DIRECTORY']
        path = pdf_location if os.path.exists(pdf_location) else \
               os.path.join(src_dir, pdf_location + '.pdf')
        pdf = PDF(path)
        ml = os.path.splitext(os.path.basename(pdf_location))[0]
        doc = Document.query.filter_by(filename=ml).first()
        for page_number in range(pdf.page_count):
            x_min, y_min, x_max, y_max = pdf.page_boxes[page_number]
            coords = pdf.text_coords(page_number)
            page = Page(page_number=page_number, doc_id=doc.id,
                        x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
            db.session.add(page)
            db.session.commit()
            for coord in coords:
                text, dims = coord
                x_min, y_min, x_max, y_max = dims
                line = TextLine(page_id=page.id, text=text, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
                db.session.add(line)
                db.session.commit()


class Page(db.Model):
    __tablename__ = 'pages'
    id = db.Column(db.Integer, primary_key=True)
    page_number = db.Column(db.Integer)
    doc_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    form_id = db.Column(db.Integer, db.ForeignKey('forms.id'))
    missing_fields = db.relationship('MissingField', backref='missing_page', lazy='dynamic')
    text_lines = db.relationship('TextLine', backref='textline_page', lazy='dynamic')
    x_min = db.Column(db.Float)
    y_min = db.Column(db.Float)
    x_max = db.Column(db.Float)
    y_max = db.Column(db.Float)


    def __repr__(self):
        return '<Page %r, %r>' % (self.page_number, self.document.filename)


    def to_json(self):
        json = {
            'id': self.id,
            'page_number': self.page_number,
            'doc_id': self.doc_id,
            'form_id': self.form_id,
            'missing_fields': [mf.to_json() for mf in self.missing_fields],
            'x_min': self.x_min,
            'x_max': self.x_max,
            'y_min': self.y_min,
            'y_max': self.y_max
        }

        return json


class MissingField(db.Model):
    __tablename__ = 'missingfields'
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id'))
    form_field_id = db.Column(db.Integer, db.ForeignKey('formfields.id'))


    def __repr__(self):
        return '<MissingField %r, %r, %r>' % (self.id, self.page_id, self.form_field_id)


    def to_json(self):
        json = {
            'id': self.id,
            'page_id': self.page_id,
            'form_field_id': self.form_field_id
        }

        return json


class TextLineSource(db.Model):
    __tablename__ = 'textlinesources'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32))
    textlines = db.relationship('TextLine', backref='textline_source', lazy='dynamic')


    @staticmethod
    def load_sources():
        for source in ['PDF', 'User']:
            db.session.add(TextLineSource(name=source))
    

    def __repr__(self):
        return '<TextLineSource %r, %r>' % (self.id, self.name)


    def to_json(self):
        json = {
            'id': self.id,
            'name': self.name,
        }

        return json


class TextLine(db.Model):
    __tablename__ = 'textlines'
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id'))
    text = db.Column(db.String)
#    x0: the distance from the left of the page to the left edge of the box.
#    y0: the distance from the bottom of the page to the lower edge of the box.
#    x1: the distance from the left of the page to the right edge of the box.
#    y1: the distance from the bottom of the page to the upper edge of the box.
    x_min = db.Column(db.Float)
    y_min = db.Column(db.Float)
    x_max = db.Column(db.Float)
    y_max = db.Column(db.Float)
    # Column for where the source of the textline is: PDF or the user cropped it
    source_id = db.Column(db.Integer, db.ForeignKey('textlinesources.id'), default=1)
    tagged_text = db.relationship('TaggedText', backref='textline', lazy='dynamic')


    def __repr__(self):
        return '<TextLine %r, %r>' % (self.id, self.textline_page)


    def to_json(self):
        json = {
            'id': self.id,
            'page_id': self.page_id,
            'text': self.text,
            'x_min': self.x_min,
            'y_min': self.y_min,
            'x_max': self.x_max,
            'y_max': self.y_max,
            'source_id': self.source_id
        }

        return json


class TaggedText(db.Model):
    __tablename__ = 'taggedtexts'
    id = db.Column(db.Integer, primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey('textlines.id'))
    field_id = db.Column(db.Integer, db.ForeignKey('formfields.id'))


    def __repr__(self):
        return '<TaggedText %r, %r, %r>' % (self.id, self.textline, self.field)


    def to_json(self):
        json = {
            'id': self.id,
            'line_id': self.line_id,
            'field_id': self.field_id
        }

        return json