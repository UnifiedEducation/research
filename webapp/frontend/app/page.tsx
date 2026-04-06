"use client";

import { useAuth } from "./msal-provider";
import FilmsByGenre from "./charts/films-by-genre";
import RatingDistribution from "./charts/rating-distribution";
import BudgetVsRating from "./charts/budget-vs-rating";
import TopDirectors from "./charts/top-directors";
import FilmsByDecade from "./charts/films-by-decade";
import AwardsByCategory from "./charts/awards-by-category";

export default function Home() {
  const { isAuthenticated, account, login, logout } = useAuth();

  if (!isAuthenticated) {
    return (
      <main className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            BMAD Film Dashboard
          </h1>
          <p className="text-gray-500 mb-6">
            Sign in with your Microsoft account to view Fabric data.
          </p>
          <button
            onClick={login}
            className="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 text-lg"
          >
            Sign In
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">
          BMAD Film Dashboard
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">
            {account?.name}
          </span>
          <button
            onClick={logout}
            className="text-sm text-red-600 hover:underline"
          >
            Sign Out
          </button>
        </div>
      </header>

      <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-7xl mx-auto">
        <FilmsByGenre />
        <RatingDistribution />
        <TopDirectors />
        <FilmsByDecade />
        <BudgetVsRating />
        <AwardsByCategory />
      </div>
    </main>
  );
}
