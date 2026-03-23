const BACKEND = 'http://127.0.0.1:8000'

async function loadData() {
  try {
    const [summaries, tasks] = await Promise.all([
      fetch(`${BACKEND}/summaries`).then(r => r.json()),
      fetch(`${BACKEND}/tasks?completed=false`).then(r => r.json())
    ])

    const summariesDiv = document.getElementById('summaries')
    summariesDiv.innerHTML = ''

    summaries.slice(0,5).forEach(s => {
      const div = document.createElement('div')
      div.className = 'card'
      // div.textContent = s.summary
      div.innerHTML = `<div class="summary-text">${s.summary}</div>`
      summariesDiv.appendChild(div)
    })

    const tasksDiv = document.getElementById('tasks')
    tasksDiv.innerHTML = ''

    tasks.slice(0,5).forEach(t => {
      const div = document.createElement('div')
      div.className = 'card'
      div.innerHTML = `
        <div class="task-title">${t.title}</div>
        <div class="task-meta">
          Due: ${t.due_date ? new Date(t.due_date).toLocaleString() : '—'}
        </div>
        <button class="push-btn" data-title="${t.title}" data-date="${t.due_date}">
          Push to Calendar
        </button>
      `
      tasksDiv.appendChild(div)
    })

    // After the buttons are appended, add event listeners
    document.querySelectorAll('.push-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          await fetch(`${BACKEND}/calendar/push`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: btn.dataset.title,
              due_date: btn.dataset.date
            })
          })

          alert('Added to Google Calendar')
        } catch (err) {
          console.error('Failed to push to calendar', err)
          alert('Failed to add event')
        }
      }
    })

  } catch (err) {
    console.error("Sidepanel load error:", err)
    document.getElementById("summaries").innerHTML =
    "<div class='card'>Failed to load summaries</div>"

  document.getElementById("tasks").innerHTML =
    "<div class='card'>Failed to load tasks</div>"
  }
}

loadData()



setInterval(loadData, 30000)

document.getElementById("refreshBtn").onclick = () => {
  loadData()
}
