
import { useEffect, useState } from 'react'
import { EmailCard } from './EmailCard'
import { TodoList } from './TodoList'
import logo from './assets/logo.png'

import { User } from '@supabase/supabase-js'
import { supabase } from './supabase'
import { Auth } from './Auth'
import {TaskModal} from './TaskModal'
type Section = 'emails'| 'summaries' | 'active' | 'completed'

type Task = {
  id: string
  title: string
  completed: boolean
  due_date?: string
  priority?: string
  context?: string
  email_id?: string

}

type Summary = {
  
  summary: string
  confidence?: number
  subject?:string
  sender?:string
  has_attachment?:boolean
}
type ClassifiedEmail = {
  id: string
  subject: string
  sender: string
  body: string
  category: 'corporate' | 'personal' | 'spam' | 'promotion'
  detailed_category: string
  confidence: number,
  has_attachment?: boolean
  attachment_count?: number
  attachment_types?: string[]
  attachments?: {
    filename: string
    type: string
  }[]
}

//  NEW: backend URL
const BACKEND_URL = 'http://127.0.0.1:8000'

export default function App() {

  /* ---------------- AUTH ---------------- */
  const [user, setUser] = useState<User | null>(null)
  const [authChecked, setAuthChecked] = useState(false)
   const [googleConnected, setGoogleConnected] = useState(false)
const [pushingTaskId, setPushingTaskId] = useState<string | null>(null)
const [pushResult, setPushResult] = useState<{
  taskId: string
  calendarLink?: string
} | null>(null)
const [emails, setEmails] = useState<ClassifiedEmail[]>([])
const [emailsLoading, setEmailsLoading] = useState(true)
const [menuOpen, setMenuOpen] = useState(false)
const [selectedTask, setSelectedTask] = useState<Task | null>(null)
const [detailsOpen, setDetailsOpen] = useState(false)
const [showFloatingMenu, setShowFloatingMenu] = useState(false)
const [searchQuery, setSearchQuery] = useState("")
const [searchMatches, setSearchMatches] = useState<HTMLElement[]>([])
const [currentMatchIndex, setCurrentMatchIndex] = useState(0)

const openDetails = (task: Task) => {
  setSelectedTask(task)
  setDetailsOpen(true)
}

const closeDetails = () => {
  setDetailsOpen(false)
}

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null)
      setAuthChecked(true)
    })

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null)
      }
    )

    return () => {
      listener.subscription.unsubscribe()
    }
  }, [])

  useEffect(() => {
  const handleScroll = () => {
    if (window.scrollY > 120) {
      setShowFloatingMenu(true)
    } else {
      setShowFloatingMenu(false)
    }
     if (menuOpen) {
      setMenuOpen(false)
    }

  }

  window.addEventListener("scroll", handleScroll)

  return () => window.removeEventListener("scroll", handleScroll)
}, [menuOpen])



useEffect(() => {
  if (!searchQuery.trim()) {
    document
      .querySelectorAll(".searchable-text")
      .forEach(el =>
        el.classList.remove("bg-yellow-200", "dark:bg-yellow-700")
      )
    setSearchMatches([])
    setCurrentMatchIndex(0)
    return
  }

  const matches: HTMLElement[] = []

  const elements = document.querySelectorAll(
    ".searchable-text"
  )

  elements.forEach(el => {
    const text = el.textContent?.toLowerCase() || ""
    if (text.includes(searchQuery.toLowerCase())) {
      el.classList.add("bg-yellow-200", "dark:bg-yellow-700")
      matches.push(el as HTMLElement)
    } else {
      el.classList.remove("bg-yellow-200", "dark:bg-yellow-700")
    }
  })

  setSearchMatches(matches)
  setCurrentMatchIndex(0)

}, [searchQuery])

const goToMatch = (direction: "next" | "prev") => {
  if (searchMatches.length === 0) return

  let newIndex = currentMatchIndex

  if (direction === "next") {
    newIndex = (currentMatchIndex + 1) % searchMatches.length
  } else {
    newIndex =
      (currentMatchIndex - 1 + searchMatches.length) %
      searchMatches.length
  }

  setCurrentMatchIndex(newIndex)

  const el = searchMatches[newIndex]

  // el.scrollIntoView({
  //   behavior: "smooth",
  //   block: "center"
  // })
  searchMatches.forEach(el =>
  el.classList.remove("ring-2","ring-red-400")
)

el.classList.add("ring-2","ring-red-400")

el.scrollIntoView({
  behavior: "smooth",
  block: "center"
})
}




  /* ---------------- UI STATE ---------------- */
  const [darkMode, setDarkMode] = useState(false)
  const [activeSection, setActiveSection] =
    useState<Section>('summaries')

  /* ---------------- DATA STATE ---------------- */
  const [tasks, setTasks] = useState<Task[]>([])


const [activeTaskSort, setActiveTaskSort] = useState<
  "default" | "due_desc" | "due_asc" | "priority_desc" | "priority_asc"
>("default")

const [completedTaskSort, setCompletedTaskSort] = useState<
  "default" | "due_desc" | "due_asc" | "priority_desc" | "priority_asc"
>("default")

  const [summaryCount, setSummaryCount] = useState(0)
  const [loading, setLoading] = useState(true)


const [summaries, setSummaries] = useState<Summary[]>([])


  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

   useEffect(() => {
  const handleClick = () => setMenuOpen(false)
  if (menuOpen) {
    window.addEventListener('click', handleClick)
  }
  return () => window.removeEventListener('click', handleClick)
}, [menuOpen])




  /* ----------------  FETCH FROM BACKEND ---------------- */
  useEffect(() => {
    if (!user) return

    async function loadData(showSpinner=false) {
        console.log("Load data called")
        if(showSpinner){
          setEmailsLoading(true)
        }
      try {
        
                         ///gmail/list   for all emails  fetching 
      
         const tasksPromise = fetch(`${BACKEND_URL}/tasks`)
        const summariesPromise = fetch(`${BACKEND_URL}/summaries`)
        const emailsPromise = fetch(`${BACKEND_URL}/emails/classified`)

        const [tasksRes, summariesRes, emailsRes] = await Promise.all([
                tasksPromise,
                summariesPromise,
                emailsPromise
          ])  
       
        const statusRes = await fetch(`${BACKEND_URL}/calendar/status`)
        const statusData = await statusRes.json()
        setGoogleConnected(statusData.connected)


        const rawTasks = await tasksRes.json()
        const rawSummaries = await summariesRes.json()
          const rawEmails = await emailsRes.json()

          


          if (rawEmails && Array.isArray(rawEmails.emails)) {
          setEmails(rawEmails.emails)
          } else {
          setEmails([])   // fallback safe
          }
          



        
        console.log("RAW SUPABASE TASKS:", rawTasks)

        const uiTasks: Task[] = rawTasks.map(
          (t: any) => ({
            id: t.id,
            title: t.title,
            completed: Boolean(t.completed),
            due_date:t.due_date || undefined,
            priority:t.priority || "medium",
            context:t.context || "",
            email_id:t.email_id || undefined
          })
        )

        setTasks(uiTasks)
        setSummaryCount(rawSummaries.length)
        setSummaries(rawSummaries)

      } catch (err) {
        console.error('Backend fetch failed', err)
         
       } 
       finally {
        setLoading(false)
        setEmailsLoading(false)
       }
    }

    loadData(true)

    // ADD THIS POLLING
   const interval = setInterval(()=>loadData(false), 10000)

    return () => clearInterval(interval)



  }, [user])





  const toggleTask = async (id: string) => {
  // 1) Find task in local state
  const task = tasks.find(t => t.id === id)
  if (!task) return

  const newCompleted = !task.completed

  // 2) Optimistic UI update
  setTasks(prev =>
    prev.map(t =>
      t.id === id ? { ...t, completed: newCompleted } : t
    )
  )

   // 3) Reset push result (avoid calendar success badge on moved tasks)
  if (pushResult?.taskId === id) {
    setPushResult(null)
  }

  try {
    // 3) Send update to backend
    // NOTE: You must store actual Supabase task.id (UUID),
    // not the index number. (Explained below.)
    await fetch(`${BACKEND_URL}/tasks/${task.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ completed: newCompleted })
    })
  } catch (err) {
    console.error("Failed to update task", err)
  }
}
 const deleteTask = async (id: string) => {
  try {
    await fetch(`${BACKEND_URL}/tasks/${id}`, {
      method: "DELETE"
    })

    // Remove from UI immediately
    setTasks(prev => prev.filter(t => t.id !== id))

  } catch (err) {
    console.error("Failed to delete task", err)
  }
}





const updateTask = async (id: string, updates: {
  title: string
  due_date?: string
  priority?: string
}) => {
  try {
    const res = await fetch(`${BACKEND_URL}/tasks/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates)
    })

    if (!res.ok) {
  throw new Error("Failed to update task")
}
    const updatedTask = await res.json()


    setTasks(prev =>
      prev.map(t => (t.id === id ? updatedTask : t))
    )

//     setTasks(prev =>
//   prev.map(t =>
//     t.id === id ? { ...t, ...updatedTask } : t
//   )
// )

  } catch (err) {
    console.error("Failed to update task", err)
  }
}

const goToSummaries = () => {
  setActiveSection("summaries")

  setTimeout(() => {
    const el = document.getElementById("summaries-section")
    if (el) el.scrollIntoView({ behavior: "smooth" })
  }, 100)
}




  const pushToCalendar = async (task: Task) => {
    let dueDateToSend = task.due_date
// If backend gave only a date (YYYY-MM-DD), assume 9 AM IST
if (dueDateToSend && !dueDateToSend.includes('T')) {
  dueDateToSend = `${dueDateToSend}T09:00:00`
}

  try {
    setPushingTaskId(task.id)
    setPushResult(null)

    const res = await fetch(`${BACKEND_URL}/calendar/push`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: task.title,
        // due_date: task.due_date
        due_date: dueDateToSend

      })
    })
    //  console.log("Pushing due_date:", task.due_date)
    console.log("Pushing due_date:", dueDateToSend)
    const data = await res.json()

    if (data.event_link) {
      setPushResult({
        taskId: task.id,
        calendarLink: data.event_link
      })

      // optional: open automatically
      // window.open(data.event_link, '_blank')
    } else {
      console.error('Calendar push failed', data)
    }
  } catch (err) {
    console.error('Calendar error', err)
  } finally {
    setPushingTaskId(null)
  }
}


  /* ---------------- AUTH GUARDS ---------------- */
  if (!authChecked) {
    return (
      <div className="h-screen flex items-center justify-center">
        Loading…
      </div>
    )
  }

  if (!user) {
    return <Auth />
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    setUser(null)
  }

  /* ---------------- RENDER (UNCHANGED UI) ---------------- */
  return (
    <div className="h-screen w-full bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100">
      {/* HEADER */}
      <header className="flex items-center justify-between p-4 border-b dark:border-zinc-700" style={{ WebkitAppRegion: 'drag' }as React.CSSProperties}>
        <div className="flex items-center gap-2">
          <img
            src={logo}
            alt="Mail Assistant"
            className="h-9 w-9 object-contain"
          />
         
          <div className="flex flex-col items-start mr-1">
          <span className="text-l font-semibold text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-purple-600 font-playfair">
           NEMO
          </span>
        
          <p className="mt-0 text-[9px] font-medium text-gray-600 dark:text-gray-400 font-roboto">
             No Emails Missed, Organized
          </p>
        </div>
        </div>
<div className="flex items-center justify-center gap-2">
  <button
  onClick={() => window.electronAPI?.toggleAlwaysOnTop()}
  style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
  title="Toggle always on top"
  className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-red-800"
>
   <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" className="h-6 w-6">
    <path d="M12 2L12 22M12 2L8 6M12 2L16 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-teal-500" />
    <circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="2" className="text-pink-500" />
  </svg>
 
 
</button>

  {/* Minimize */}
  <button
    onClick={() => window.electronAPI?.minimize()}
    style={{ WebkitAppRegion: 'no-drag' }as React.CSSProperties}
    title="Minimize"
    className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-red-800"
  >
    —
  </button>

  {/* Close */}
  <button
    onClick={() => window.electronAPI?.close()}
    style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}

    title="Close"
    className="p-1 rounded hover:bg-red-200 dark:hover:bg-red-800"
  >
    ×
  </button>
  {/* Reset to Rightmost */}
        <button
          onClick={() => window.electronAPI?.resetToRightmost()}
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
          title="Reset to Rightmost"
          className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-green-800"
        >
          <svg
    className="w-5 h-5 text-zinc-600 dark:text-zinc-400"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    viewBox="0 0 24 24"
  >
    {/* Window outline */}
    <rect x="3" y="4" width="18" height="16" rx="2" />
    
    {/* Right sidebar area */}
    <line x1="15" y1="4" x2="15" y2="20" />
  </svg>
        </button>
</div>



<div className="flex items-center justify-center gap-2">        

  <p></p>
  <p></p>
</div>


        <div className="flex items-center gap-3">
          {/* Logout */}
          <button
            onClick={handleLogout}
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}

            title="Logout"
            className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800"
          >
            <svg
              className="w-5 h-5 text-zinc-600 dark:text-zinc-400"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path d="M17 16l4-4m0 0l-4-4m4 4H7" />
              <path d="M7 8v8" />
            </svg>
          </button>
          <div
  className="relative group"
  style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
>
  <button
    className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400"
  >
    ⓘ
  </button>

  <div className="absolute right-0 mt-2 w-max px-2 py-1 text-xs rounded-md 
                  bg-zinc-800 text-white dark:bg-zinc-700
                  opacity-0 group-hover:opacity-100
                  transition-opacity duration-200 pointer-events-none z-50">
    Shortcut: Ctrl + Q
  </div>
</div>

          {/* Theme toggle */}
          <button
            onClick={() => setDarkMode(!darkMode)}
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}

            className="relative w-11 h-6 rounded-full bg-zinc-300 dark:bg-zinc-700 transition-colors"
          >
            <span
              className={`absolute top-0.5 left-0.5 flex items-center justify-center h-5 w-5 rounded-full bg-white shadow transition-transform
                ${darkMode ? 'translate-x-5' : 'translate-x-0'}
              `}
            >
              {darkMode ? (
                <svg
                  className="w-3 h-3 text-zinc-700"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z" />
                </svg>
              ) : (
                <svg
                  className="w-3 h-3 text-zinc-500"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
              )}
            </span>
          </button>
          
        </div>
      </header>

      <main className="p-4 space-y-3 overflow-y-auto min-h-screen  bg-white dark:bg-zinc-900">
        {!googleConnected && (
  <div className="mb-3 p-3 rounded-lg bg-blue-50 dark:bg-zinc-800 border border-blue-200 dark:border-zinc-700">
    <p className="text-sm text-zinc-700 dark:text-zinc-300 mb-2">
      Connect Google account for calendar and inbox access.
    </p>

    <button
      // onClick={() => window.open(`${BACKEND_URL}/calendar/auth`, '_blank')}
      onClick={() => {
  const authWindow = window.open(`${BACKEND_URL}/calendar/auth`, '_blank')

  const interval = setInterval(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/calendar/status`)
      const data = await res.json()

      if (data.connected) {
        setGoogleConnected(true)
        clearInterval(interval)
        authWindow?.close()
      }
    } catch (err) {
      console.error('Status check failed')
    }
  }, 1000)

  // stop polling after 15 seconds (safety)
  setTimeout(() => clearInterval(interval), 15000)
}}

      className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
    >
      Connect Google Account
    </button>
  </div>
)}



{googleConnected && (
  <div className="mb-2 flex items-center justify-between gap-3">
    
    {/* Left side - Connected badge */}
    {/* <div className="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-green-500 to-emerald-600 px-3 py-1 text-xs font-semibold text-white shadow-md">


      <span className="h-2 w-2 rounded-full bg-white animate-ping"></span>
      Connected to Google
    </div> */}




    <div className="flex items-center gap-2">
      <span className="h-2 w-2 rounded-full bg-blue-700 animate-ping"></span>
  <img
    src="https://www.gstatic.com/images/branding/product/1x/gmail_48dp.png"
    alt="Google Connected"
    
    className="h-5 w-5 opacity-90 hover:opacity-100"
    title="Google Connected"
  />
</div>
    {/* SEARCH BAR */}
{/* <div className="flex items-center gap-2 flex-1 max-w-sm"> */}
  <div
className={`
flex items-center gap-2 flex-1 max-w-sm min-w-0
${showFloatingMenu ? 
"fixed top-3 left-1/2 -translate-x-1/2 z-50 shadow-lg bg-white dark:bg-zinc-900 p-2 rounded-lg" 
: ""}
`}
>
  
  <input
    type="text"
    placeholder="Search..."
    value={searchQuery}
    onChange={(e) => setSearchQuery(e.target.value)}
    onKeyDown={(e) => {
  if (e.key === "Escape") {
    setSearchQuery("");
    setCurrentMatchIndex(0);
  }
}}
    className="
      w-full
      px-3 py-1.5
      text-sm
      rounded-md
      border
      border-zinc-300
      dark:border-zinc-700
      bg-white
      dark:bg-zinc-900
      text-zinc-700
      dark:text-zinc-200
      focus:outline-none
      focus:ring-2
      focus:ring-indigo-500
    "
  />


  {searchMatches.length > 0 && (
    <div className="flex items-center gap-1 text-xs">
      
      <button
        onClick={() => goToMatch("prev")}
        className="px-2 py-1 rounded bg-zinc-200 dark:bg-zinc-700"
      >
        ↑
      </button>

      <button
        onClick={() => goToMatch("next")}
        className="px-2 py-1 rounded bg-zinc-200 dark:bg-zinc-700"
      >
        ↓
      </button>
      {searchQuery &&(
      <button
        onClick={() => {
          setSearchQuery("");
          setCurrentMatchIndex(0);
        }}
        className="px-2 py-1 rounded bg-red-200 dark:bg-red-700 text-red-700 dark:text-red-200"
      >
        ✕
      </button>
    
)}
      <span className="text-zinc-500 dark:text-zinc-400">
        {currentMatchIndex + 1}/{searchMatches.length}
      </span>

    </div>
  )}

</div>

    {/* Right side - Hamburger Dropdown */}
    {!showFloatingMenu && (
    <div
      className="relative"
      style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
    >
      <button
        onClick={(e) => {
          e.stopPropagation()
          setMenuOpen(!menuOpen)}}
        className="p-2 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800"
      >
        {/* 3-line SVG icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5 text-zinc-700 dark:text-zinc-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {menuOpen && (
        <div className="absolute right-0 mt-2 w-44 rounded-lg shadow-lg bg-white dark:bg-zinc-800 border dark:border-zinc-700 z-50">
          
          {[
            { label: 'Emails', value: 'emails' },
            { label: 'Summaries', value: 'summaries' },
            { label: 'Active Tasks', value: 'active' },
            { label: 'Completed Tasks', value: 'completed' }
          ].map(item => (
            <button
              key={item.value}
              onClick={(e) => {
                e.stopPropagation()
                setActiveSection(item.value as Section)
                setMenuOpen(false)
              }}
              className="block w-full text-left px-4 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-700"
            >
              {item.label}
            </button>
          ))}

        </div>
      )}
    </div>
    )}
  </div>
    )}








        {/*Emails */}
        <SectionHeader
      title="EMAILS"
        open={activeSection === 'emails'}
      onClick={() => setActiveSection('emails')}
        />
        {activeSection === 'emails' && (
  <div className="space-y-3 min-h-screen  bg-white dark:bg-zinc-900">

        {emailsLoading && (
      <div className="flex justify-center py-6">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )}

    
    {emails.length === 0 && (
  <div className="flex items-center gap-2 text-sm text-zinc-500">
    {emailsLoading && (
      <div className="h-3 w-3 border-2 border-pink-400 border-t-transparent rounded-full animate-spin" />
    )}
    No unread emails
    <div className="h-3 w-3 border-2 border-pink-400 border-t-transparent rounded-full animate-spin" />
  </div>
)}

    {!emailsLoading &&emails.map(email => (
      <div
        key={email.id}
        data-searchable-text={`${email.subject} ${email.sender} ${email.body}`}
        className="p-3 rounded-lg border dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition"
      >
        <div className="flex justify-between items-start">
          <div>
            <p className="font-medium searchable-text">{email.subject}</p>
            <p className="text-xs text-pink-500 searchable-text">
              {email.sender}
            </p>
   <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-1 searchable-text">
  {email.body?.slice(0, 140)}...
</p>
          </div>
       

          <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 ">
            {/* {email.detailed_category} */}
             {email.category}
          </span>
        </div>

        {/* <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-300 line-clamp-3">
          {email.body}
        </p> */}

      {email.has_attachment && (
  <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
    📎 {email.attachment_count} attachment(s)
  </div>
)}


        {email.attachments && email.attachments.length > 0 && (
  <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
    {email.attachments.map((file, i) => (
      <div key={i}>
        📄 {file.filename} ({file.type})
      </div>
    ))}
  </div>
)}



        <div className="mt-2 text-xs font-medium text-blue-600 dark:text-blue-400">
        Generated by Nemo
       </div>
       
       <div className="mt-2 flex items-center gap-2">

       <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
  {/* Category: {email.category} */}
  {/* <span className="opacity-60">•</span> */}
  Confidence: {(email.confidence * 100).toFixed(1)}%
</p> 
  
 
   <button
  onClick={goToSummaries}
  className="mt-2 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
>

  View Summary →
</button>
   </div>


      </div>
    ))}
  </div>
)}



        {/* SUMMARIES */}
        <SectionHeader
          title="SUMMARIES"
          open={activeSection === 'summaries'}
          onClick={() => setActiveSection('summaries')}
        />

        {activeSection === 'summaries' && (
          <div id="summaries-section" className="space-y-3">
            {loading && <p className="text-sm">Loading summaries…</p>}
              
{summaries.map((s, i) => (
  <div
    key={i}
    // data-searchable-text={`${s.summary} ${s.subject ?? ""} ${s.sender ?? ""}`}
    className="searchable-text"
  >
  <EmailCard
    key={i}
    summary={s.summary}
    confidence={s.confidence}
    subject={s.subject}
    sender={s.sender}
    has_attachment={s.has_attachment}
  />
  </div>
))}


          </div>
        )}

        {/* ACTIVE TASKS */}
        <SectionHeader
          title="ACTIVE TASKS"
          open={activeSection === 'active'}
          onClick={() => setActiveSection('active')}
        />
        


        {activeSection === 'active' && (
  
           <>
  <div className="flex justify-end mb-4">
    <div className="relative inline-block w-52">
      <select
        value={activeTaskSort}
        onChange={(e) => setActiveTaskSort(e.target.value as typeof activeTaskSort)}
        className="
          w-full
          appearance-none
          bg-white dark:bg-zinc-900
          border border-zinc-300 dark:border-zinc-700
          text-sm text-zinc-700 dark:text-zinc-200
          px-4 py-2 pr-10
          rounded-lg
          shadow-sm
          hover:border-zinc-400 dark:hover:border-zinc-500
          focus:outline-none
          focus:ring-2 focus:ring-indigo-500/40
          focus:border-indigo-500
          transition-all duration-200
          cursor-pointer
        "
      >
        <option value="default">Default</option>
        <option value="due_desc">Due Date (new)</option>
        <option value="due_asc">Due Date (old)</option>
        <option value="priority_desc">Priority High → Low</option>
        <option value="priority_asc">Priority Low → High</option>
      </select>

      {/* Custom Dropdown Icon */}
      <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-zinc-400 dark:text-zinc-500">
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>
  </div>
        




          <TodoList
            mode="active"
            tasks={tasks}
            onToggle={toggleTask}
            googleConnected={googleConnected}
             onPush={pushToCalendar}
            pushingTaskId={pushingTaskId}
           pushResult={pushResult}
           onOpenDetails={(task) => setSelectedTask(task)}
           sortType={activeTaskSort}
           onDelete={deleteTask}
            
          />
          </>
       )} 

        {/* COMPLETED TASKS */}
        <SectionHeader
          title="COMPLETED TASKS"
          open={activeSection === 'completed'}
          onClick={() => setActiveSection('completed')}
        />

        {activeSection === 'completed' && (
          <>
    <div className="flex justify-end mb-4">
      <div className="relative inline-block w-52">
        <select
          value={completedTaskSort}
          onChange={(e) =>
            setCompletedTaskSort(e.target.value as typeof completedTaskSort)
          }
          className="
            w-full
            appearance-none
            bg-white dark:bg-zinc-900
            border border-zinc-300 dark:border-zinc-700
            text-sm text-zinc-700 dark:text-zinc-200
            px-4 py-2 pr-10
            rounded-lg
            shadow-sm
            hover:border-zinc-400 dark:hover:border-zinc-500
            focus:outline-none
            focus:ring-2 focus:ring-indigo-500/40
            focus:border-indigo-500
            transition-all duration-200
            cursor-pointer
          "
        >
          <option value="default">Default</option>
          <option value="due_desc">Due Date (new)</option>
          <option value="due_asc">Due Date (old)</option>
          <option value="priority_desc">Priority High → Low</option>
          <option value="priority_asc">Priority Low → High</option>
        </select>

        <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-zinc-400 dark:text-zinc-500">
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>



          <TodoList
            mode="completed"
            tasks={tasks}
            onToggle={toggleTask}
            googleConnected={googleConnected}
            onPush={pushToCalendar}
            pushingTaskId={pushingTaskId}
            pushResult={pushResult}
            // onOpenDetails={openDetails}
            onOpenDetails={(task) => setSelectedTask(task)}
            sortType={completedTaskSort}
            onDelete={deleteTask}
          />
          </>
        )}
      </main>

      {selectedTask && (
     <>
  <TaskModal
    task={selectedTask}
    email={
  selectedTask.email_id
    ? emails.find(e => String(e.id) === String(selectedTask.email_id))
    : undefined
}
    onClose={() => setSelectedTask(null)}
    onUpdate={updateTask}
  />
  </>
)}
{/* Floating Hamburger Menu */}
{showFloatingMenu && (
  <div
    className="fixed top-20 right-4 z-50"
    style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
  >
    <div className="relative">
      <button
        onClick={(e) => {
          e.stopPropagation()
          setMenuOpen(!menuOpen)
        }}
        className="p-3 rounded-full shadow-lg bg-white dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 border dark:border-zinc-700"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5 text-zinc-700 dark:text-zinc-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {menuOpen && (
        <div className="absolute right-0 mt-2 w-44 rounded-lg shadow-lg bg-white dark:bg-zinc-800 border dark:border-zinc-700 z-50">
          {[
            { label: 'Emails', value: 'emails' },
            { label: 'Summaries', value: 'summaries' },
            { label: 'Active Tasks', value: 'active' },
            { label: 'Completed Tasks', value: 'completed' }
          ].map(item => (
            <button
              key={item.value}
              onClick={(e) => {
                e.stopPropagation()
                setActiveSection(item.value as Section)
                setMenuOpen(false)
              }}
              className="block w-full text-left px-4 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-700"
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  </div>
)}

    </div>
  )
}

/* ---------- Section Header ---------- */
function SectionHeader({
  title,
  open,
  onClick
}: {
  title: string
  open: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}

      className={`w-full flex justify-between items-center px-3 py-2 rounded-lg text-sm font-medium
        ${open
          ? 'bg-zinc-200 dark:bg-zinc-800'
          : 'hover:bg-zinc-100 dark:hover:bg-zinc-800'}
      `}
    >
      {title}
      <span className="text-xs">{open ? '−' : '+'}</span>
    </button>
  )
}
