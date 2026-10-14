from urllib.parse import urlsplit


class Browser:
    def __init__(self, execution, data):
        self.execution = execution
        self.screens = data / 'screenshots'
        self.screens.mkdir(exist_ok=True)

    def inspect(self, project, actions=None, viewport=None):
        status = self.execution.status(project)
        if not status.get('running') or not status.get('ready'):
            raise ValueError('Inicie o projeto e aguarde a URL responder')
        from playwright.sync_api import sync_playwright, expect
        viewport = viewport or {'width':1280,'height':800}
        if (not isinstance(viewport,dict) or set(viewport) != {'width','height'}
                or any(type(v) is not int for v in viewport.values())
                or not 320 <= viewport['width'] <= 2560 or not 320 <= viewport['height'] <= 1920):
            raise ValueError('Viewport inválido; use largura 320–2560 e altura 320–1920.')
        url = status['url']
        origin = urlsplit(url)
        report = {'url':url,'errors':[],'http':[],'blocked':[],'actions':[],'viewport':viewport}
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception:
                # Usa o Edge existente, sem instalar um navegador no Windows.
                browser = pw.chromium.launch(headless=True,channel='msedge')
            try:
                context = browser.new_context(service_workers='block',accept_downloads=False,viewport=viewport)
                def route(req):
                    parsed = urlsplit(req.request.url)
                    if parsed.scheme in ('data','blob') or (parsed.scheme=='http' and parsed.hostname==origin.hostname and parsed.port==origin.port):
                        req.continue_()
                    else:
                        report['blocked'].append(req.request.url)
                        req.abort()
                context.route('**/*',route)
                page = context.new_page()
                page.on('pageerror',lambda err:report['errors'].append(str(err)))
                navigation_status = None
                def response_received(response):
                    nonlocal navigation_status
                    report['http'].append({'status':response.status,'url':response.url})
                    if response.request.is_navigation_request() and response.request.frame == page.main_frame:
                        navigation_status = response.status
                page.on('response',response_received)
                response = page.goto(url,wait_until='domcontentloaded',timeout=20000)
                for action in (actions or [])[:20]:
                    if action.get('type') == 'click':
                        page.locator(action['selector']).click(timeout=5000)
                    elif action.get('type') == 'fill':
                        page.locator(action['selector']).fill(str(action.get('value','')),timeout=5000)
                    elif action.get('type') == 'select':
                        page.locator(action['selector']).select_option(str(action.get('value','')),timeout=5000)
                    elif action.get('type') == 'expect_text':
                        expect(page.locator(action['selector'])).to_contain_text(str(action.get('value','')),timeout=5000)
                    else:
                        raise ValueError('Ação de navegador não permitida')
                    report['actions'].append(action)
                report.update(status=navigation_status or (response.status if response else None),title=page.title(),
                              text=page.locator('body').inner_text()[:12000],
                              elements=page.locator('input,button,a,select,textarea').evaluate_all('(els)=>els.slice(0,80).map(e=>({tag:e.tagName,id:e.id,text:e.innerText,name:e.name}))'),
                              screenshot=f'/api/screenshots/{project}.png')
                report['layout'] = page.evaluate('({width:innerWidth,documentWidth:document.documentElement.scrollWidth,height:innerHeight})')
                report['http_errors'] = [entry for entry in report['http'] if entry['status']>=400]
                page.screenshot(path=str(self.screens/f'{project}.png'),full_page=True)
                return report
            finally:
                browser.close()
