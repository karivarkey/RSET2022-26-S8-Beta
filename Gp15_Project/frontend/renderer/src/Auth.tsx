
import { useState,useEffect } from 'react'
import { supabase } from './supabase'
import logo from './assets/logo.png';
export function Auth() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [darkMode, setDarkMode] = useState(true)
  const [signInLoading, setSignInLoading] = useState(false)
const [signUpLoading, setSignUpLoading] = useState(false)

   
   useEffect(() => {
  if (darkMode) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}, [darkMode])

  



  const signIn = async () => {
    setSignInLoading(true)
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password
    })
    if (error) setErrorMessage(error.message)
    setSignInLoading(false)
  }

  const signUp = async () => {
    setSignUpLoading(true)
    const { error } = await supabase.auth.signUp({
      email,
      password
    })
    if (error) setErrorMessage(error.message)
    setSignUpLoading(false)
  }

  return (
           
    



    <div className="h-screen flex flex-col justify-center p-6 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100">
       <div className="flex gap-7 absolute top-10 right-10">

        <button
  onClick={() => setDarkMode(!darkMode)}
className="p-2 rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-700 transition"
>
  
<div
  onClick={() => setDarkMode(!darkMode)}
  className="relative w-12 h-6 bg-zinc-300 dark:bg-zinc-700 rounded-full cursor-pointer transition-colors"
>
  <span
    className={`absolute top-0.5 left-0.5 flex items-center justify-center h-5 w-5 rounded-full bg-white shadow transition-transform
      ${darkMode ? 'translate-x-6' : 'translate-x-0'}
    `}
  >
    {darkMode ? (
      // Moon icon
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
      // Sun icon
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
</div>





</button>

    <button onClick={() => window.electronAPI?.minimize()}>_</button>
    <button onClick={() => window.electronAPI?.toggleAlwaysOnTop()}>
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" className="h-6 w-6">
    <path d="M12 2L12 22M12 2L8 6M12 2L16 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-teal-500" />
    <circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" strokeWidth="2" className="text-pink-500" />
  </svg>
      
      </button>
    <button onClick={() => window.electronAPI?.close()}>X</button>
  </div>
      <br></br>
      <br></br>
   <div className="flex justify-center items-center w-full mb-4">

      <img
    src={logo}        
    alt="NEMO Logo"
    className="w-12 h-12 -mr-3 animate-pulse"
  />
      </div>
       <h2 className="text-2xl font-bold mb-6 text-center">
  Welcome to <span className="text-teal-500">NEMO</span>
</h2>
    


<form
  className="w-full"
  onSubmit={(e) => {
    e.preventDefault(); 
    signIn();           
  }}
>

      <input

        className="w-full mb-4 p-3 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 dark:bg-zinc-900"

        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />

      <input
        className="w-full mb-4 p-3 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 dark:bg-zinc-900"

        type="password"
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
      />
 
    
<div className="absolute inset-0 overflow-hidden pointer-events-none">
  <div
    className={`absolute w-72 h-72 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob top-10 left-10 ${
      darkMode ? 'bg-purple-900' : 'bg-teal-300'
    }`}
  ></div>

  <div
    className={`absolute w-72 h-72 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000 top-40 right-20 ${
      darkMode ? 'bg-pink-700' : 'bg-pink-500'
    }`}
  ></div>

  <div
    className={`absolute w-72 h-72 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000 bottom-20 left-40 ${
      darkMode ? 'bg-blue-800' : 'bg-purple-500'
    }`}
  ></div>
</div>

<div className="absolute inset-0 overflow-hidden pointer-events-none">
  <div
    className={`absolute w-72 h-72 rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob top-10 left-10 bg-teal-400 ${
      darkMode ? 'bg-teal-400' : 'bg-teal-300'
    }`}
  ></div>

  <div
    className={`absolute w-72 h-72 rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob animation-delay-2000 top-40 right-20 ${
      darkMode ? 'bg-pink-400' : 'bg-pink-300'
    }`}
  ></div>

  <div
    className={`absolute w-72 h-72 rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob animation-delay-4000 bottom-20 left-40 ${
      darkMode ? 'bg-purple-400' : 'bg-purple-400'
    }`}
  ></div>
</div>




      <button
       type="submit"
         
        onClick={signIn}
        disabled={signInLoading}

        className="w-full mb-3 p-3 bg-teal-500 hover:bg-teal-600 transition text-white rounded-lg font-semibold"

      >

        {signInLoading && (
    <svg
      className="animate-spin h-5 w-5 text-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      ></circle>
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      ></path>
    </svg>
  )}
  {signInLoading ? 'Signing In...' : 'Sign In'}
      
      </button>

      <button
      type="button"
        onClick={signUp}
        disabled={signUpLoading}
        className="w-full p-3 border border-zinc-400 dark:border-zinc-600 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-700 transition"

      >
        {signUpLoading ? 'Creating Account...' : 'Create Account'}
      </button>
      </form>
  
      {errorMessage && (
  <div className="fixed inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm">
    <div className="bg-white dark:bg-zinc-800 p-6 rounded-xl shadow-xl w-80">
      <h3 className="text-lg font-semibold mb-2 text-red-500">
        Authentication Error
      </h3>
      <p className="text-sm mb-4">{errorMessage}</p>
      <button
        onClick={() => setErrorMessage('')}
        className="w-full p-2 bg-black dark:bg-white dark:text-black text-white rounded"
      >
        Close
      </button>
    
    </div>
  </div>
)}
    </div>
  )
}
