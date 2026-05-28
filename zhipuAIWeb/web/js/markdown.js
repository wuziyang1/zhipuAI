/**
 * Markdown 渲染
 */
const Markdown = {
  init() {
    if (typeof marked !== 'undefined') {
      marked.setOptions({
        breaks: true,
        gfm: true,
      });
    }
  },

  render(text) {
    if (typeof marked !== 'undefined') {
      return marked.parse(text);
    }
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  },
};

Markdown.init();
