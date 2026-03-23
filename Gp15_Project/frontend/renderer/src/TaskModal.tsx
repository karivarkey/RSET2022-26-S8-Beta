import React from "react"

type TaskModalProps = {
  task: any
  email: any
  onClose: () => void
   onUpdate: (id: string, updates: {
    title: string
    due_date?: string
    priority?: string
  }) => void
}

export function TaskModal({ task, email, onClose,onUpdate }: TaskModalProps) {
  


const [isEditing, setIsEditing] = React.useState(false)
  const [title, setTitle] = React.useState("")
  const [dueDate, setDueDate] = React.useState("")
  const [priority, setPriority] = React.useState("Medium")

 React.useEffect(() => {
    if (task) {
      setTitle(task.title)
      setDueDate(task.due_date ? task.due_date.split("T")[0] : "")
      setPriority(task.priority || "Medium")
    }
  }, [task])

  if (!task) return null



  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
      <div className="bg-white dark:bg-zinc-900 p-5 rounded-xl shadow-xl w-full max-w-lg">
    
        {/* Header */}
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-100">
            Task Details
          </h2>
          <button onClick={onClose} className="text-xl">×</button>
        </div>

        {/* Task Info */}
        <div className="space-y-2 text-sm">
          
          <p>
  <strong>Title:</strong>{" "}
  {isEditing ? (
    <input
      value={title}
      onChange={e => setTitle(e.target.value)}
      className="w-full
    rounded-lg
    border
    px-3 py-2
    bg-white
    text-zinc-900
    border-zinc-300
    focus:outline-none focus:ring-2 focus:ring-blue-500
    dark:bg-zinc-800
    dark:text-zinc-100
    dark:border-zinc-600"
    />
  ) : (
    task.title
  )}
</p>
          
          <p>
  <strong>Due Date:</strong>{" "}
  {isEditing ? (
    <input
      type="date"
      value={dueDate}
      onChange={e => setDueDate(e.target.value)}
      className="w-full
    rounded-lg
    border
    px-3 py-2
    bg-white
    text-zinc-900
    border-zinc-300
    focus:outline-none focus:ring-2 focus:ring-blue-500
    dark:bg-zinc-800
    dark:text-zinc-100
    dark:border-zinc-600"
    />
  ) : (
    task.due_date && new Date(task.due_date).toLocaleString()
  )}
</p>
          
            <p>
  <strong>Priority:</strong>{" "}
  {isEditing ? (
    <select
      value={priority}
      onChange={e => setPriority(e.target.value)}
      className="w-full
    rounded-lg
    border
    px-3 py-2
    bg-white
    text-zinc-900
    border-zinc-300
    focus:outline-none focus:ring-2 focus:ring-blue-500
    dark:bg-zinc-800
    dark:text-zinc-100
    dark:border-zinc-600"
    >
      <option value="high">High</option>
      <option value="medium">Medium</option>
      <option value="low">Low</option>
    </select>
  ) : (
    task.priority
  )}
</p>

          {task.context && (
            <p><strong>Context:</strong> {task.context}</p>
          )}

          {task.source_sentence && (
            <p className="italic text-zinc-500">
              "{task.source_sentence}"
            </p>
          )}
        </div>

        <hr className="my-3" />

        {/* Email Preview */}
        {email && (
          <div className="text-sm">
            <p className="font-semibold">{email.subject}</p>
            <p className="text-xs text-pink-500">{email.sender}</p>

            <p className="mt-2 whitespace-pre-line text-zinc-700 dark:text-zinc-300 line-clamp-5">
              {email.body}
            </p>
          </div>
        )}
        
        {/* Footer actions */}
        <div className="mt-4 text-right">
          {email?.gmail_id && (
            <a
              href={`https://mail.google.com/mail/u/0/#inbox/${email.gmail_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mr-4 text-blue-600"
            >
              Open in Gmail
            </a>
           
          )}
          {!task.completed &&(!isEditing ? (
  <button
    onClick={() => setIsEditing(true)}
    className="mr-3 px-3 py-1 rounded bg-blue-600 text-white"
  >
    Edit
  </button>
) : (
  <button
    onClick={() => {
      onUpdate(task.id, {
        title,
        due_date: dueDate ? `${dueDate}T09:00:00` : undefined,
        priority
      })
      setIsEditing(false)

    }}
    className="mr-3 px-3 py-1 rounded bg-green-600 text-white"
  >
    Save
  </button>
)
)}






          <button
            onClick={onClose}
            className="px-3 py-1 rounded bg-zinc-200 dark:bg-zinc-700"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  )
}