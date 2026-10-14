'use strict';

// Authorization belongs to new requests in this browser tab, never to old proposals.
class AutoApproval {
    constructor(storage) {
        this.storage = storage;
        try { this.jobs = JSON.parse(storage.getItem('studio-auto-approval-jobs') || '{}'); }
        catch { this.jobs = {}; }
        if (!this.jobs || typeof this.jobs !== 'object' || Array.isArray(this.jobs)) this.jobs = {};
        this.busy = new Map();
    }
    remember() { this.storage.setItem('studio-auto-approval-jobs', JSON.stringify(this.jobs)); }
    authorize(job, project) { this.jobs[job] = project; this.remember(); }
    forget(job) { delete this.jobs[job]; this.remember(); }
    disable(project) {
        for (const job of Object.keys(this.jobs)) if (this.jobs[job] === project) delete this.jobs[job];
        this.remember();
    }
    async apply(project, proposals, handlers) {
        if (this.busy.has(project)) return this.busy.get(project);
        const jobs = [...new Set(proposals.filter(p => this.jobs[p.job] === project).map(p => p.job))];
        if (!jobs.length) return false;
        const work = this.run(project, proposals, jobs, handlers);
        this.busy.set(project, work);
        try { return await work; } finally { this.busy.delete(project); }
    }
    async run(project, proposals, jobs, {enabled, preflight, apply, report}) {
        for (const job of jobs) {
            let count = 0;
            const items = proposals.filter(p => p.job === job);
            try {
                if (!enabled() || this.jobs[job] !== project) continue;
                // Check the whole group before saving its first file.
                await preflight(items);
                for (const item of items) {
                    if (!enabled() || this.jobs[job] !== project) break;
                    await apply(item);
                    count++;
                }
                if (count) report(`${count} arquivo(s) aprovado(s) e salvo(s) automaticamente.`, count);
            } catch (error) {
                report(`Autoaprovação pausada: ${error.message} ${count} arquivo(s) salvo(s). As propostas restantes aguardam revisão manual.`, count);
            } finally {
                delete this.jobs[job]; this.remember();
            }
        }
        return true;
    }
}
