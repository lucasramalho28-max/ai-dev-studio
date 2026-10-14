from flask import Blueprint, jsonify, request


def logistics_blueprint(project, body, confirmed, logistics, dashboards, jobs):
    bp = Blueprint('logistics', __name__)

    @bp.get('/api/projects/<pid>/logistics')
    def state(pid):
        return jsonify(logistics.state(project(pid)))

    @bp.post('/api/projects/<pid>/logistics/uploads')
    def upload(pid):
        project(pid)
        if 'file' not in request.files:
            raise ValueError('Selecione uma base para análise')
        return jsonify(logistics.save_upload(pid, request.files['file'])), 201

    @bp.post('/api/projects/<pid>/logistics/synthetic')
    def synthetic(pid):
        b = body()
        confirmed(b)
        return jsonify(logistics.synthetic_sla(project(pid))), 201

    @bp.post('/api/projects/<pid>/logistics/analyze')
    def analyze(pid):
        b = body()
        return jsonify(logistics.analyze(project(pid), str(b.get('upload_id', ''))))

    @bp.post('/api/projects/<pid>/logistics/indicators')
    def indicator(pid):
        b = body()
        confirmed(b)
        return jsonify(logistics.save_indicator(project(pid), b)), 201

    @bp.post('/api/projects/<pid>/logistics/memory')
    def memory(pid):
        b = body()
        confirmed(b)
        return jsonify(logistics.save_memory(project(pid), str(b.get('category', '')), str(b.get('key', '')), b.get('value'))), 201

    @bp.post('/api/projects/<pid>/logistics/dashboard')
    def dashboard(pid):
        b = body()
        confirmed(b)
        pid = project(pid)

        def run(job, emit, cancel):
            return dashboards.generate(pid, b, job, emit, cancel)

        return jsonify(job=jobs.start('logistics_dashboard', pid, b, run))

    return bp
