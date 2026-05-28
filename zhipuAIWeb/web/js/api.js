/**
 * 后端 API 调用
 */
const API = {
  /**
   * 解析用户输入为题目和作答
   */
  parseInput(text) {
    const solutionMatch = text.match(/(?:作答|解答|我的答案)[：:]\s*([\s\S]+)/i);
    const questionMatch = text.match(/题目[：:]\s*([\s\S]*?)(?=(?:作答|解答|我的答案)[：:]|$)/i);

    if (!questionMatch || !solutionMatch) {
      return null;
    }

    const question = questionMatch[1].trim();
    const studentSolution = solutionMatch[1].trim();

    if (!question || !studentSolution) return null;
    return { question, studentSolution };
  },

  async diagnose(question, studentSolution, settings) {
    const res = await fetch(`${settings.apiBase}/diagnose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        student_solution: studentSolution,
        include_analysis: settings.includeAnalysis,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      const detail = data.detail;
      const msg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((e) => e.msg).join('; ')
          : '请求失败';
      throw new Error(msg);
    }

    return data;
  },

  formatDiagnosisResponse(data) {
    const lines = [];
    const tags = [];

    if (data.process_correct !== null) {
      tags.push(data.process_correct ? '过程正确' : '过程错误');
    }
    if (data.result_correct !== null) {
      tags.push(data.result_correct ? '结果正确' : '结果错误');
    }
    if (data.parsed?.error_type && data.parsed.error_type !== '无错误') {
      tags.push(`错误类型：${data.parsed.error_type}`);
    }
    if (data.parsed?.error_step) {
      tags.push(`出错步骤：第 ${data.parsed.error_step} 步`);
    }

    if (tags.length) {
      lines.push(`> **诊断摘要**：${tags.join(' · ')}`);
      lines.push('');
    }

    lines.push(data.diagnosis || '（无诊断内容）');
    return lines.join('\n');
  },
};
