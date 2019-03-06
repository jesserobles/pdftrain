db.create_all()
Document.insert_documents()
FormField.insert_fields()
TextLineSource.load_sources()

# Add 'Other' to forms table
form = Form(form_name='Other')
db.session.add(form)

filename = 'ML15009A030'
Document.load_pdf(filename)
doc = Document.query.filter_by(filename=filename).first()
page_number = 1
page = Page.query.filter(Page.doc_id == doc.id).filter(Page.page_number == page_number).first()
form = Form.query.filter_by(form_name='Form 366').first()

# update page form
page.page_form = form

# get form fields and text line
top_form_field = FormField.query.filter_by(name='Top Form 366').first()
bottom_form_field = FormField.query.filter_by(name='Bottom Form 366').first()
top_textline = TextLine.query.filter_by(text='NRC  FORM  366 \n(01-2014) \n').first()

# add tag for field: Top Form 366
tagged_text = TaggedText(textline=top_textline, field=top_form_field)
db.session.add(tagged_text)

# add missing tag
missing_field = MissingField(missing_page=page, field=bottom_form_field)
db.session.add(missing_field)

db.session.commit()
