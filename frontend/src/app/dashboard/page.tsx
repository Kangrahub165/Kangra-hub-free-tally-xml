'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  ArrowRight, 
  FileText, 
  CheckCircle2, 
  Sparkles, 
  Download,
  Layers, 
  History, 
  Clock, 
  ChevronRight,
  Receipt,
  ShoppingCart,
  Coins,
  CreditCard,
  User,
  Star,
  Check,
  AlertCircle,
  Save,
  Phone,
  Mail,
  ShieldCheck,
  UserCheck
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { 
  getUserUsage, 
  getUserConversions, 
  UsageInfo, 
  ConversionJobSummary,
  getUserProfile,
  updateUserProfile,
  submitReview,
  getMyReview,
  ReviewItem
} from '@/lib/api';
import { useAuth } from '@/components/auth/AuthProvider';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { GoldTick } from '@/components/ui/GoldTick';
import { SubscriptionModal } from '@/components/SubscriptionModal';

export default function UserDashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user, isStaff, isGold } = useAuth();
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [conversions, setConversions] = useState<ConversionJobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showSubModal, setShowSubModal] = useState(false);

  // Profile management states
  const [fullName, setFullName] = useState(user?.fullName || '');
  const [mobileNumber, setMobileNumber] = useState(user?.mobileNumber || '');
  const [gender, setGender] = useState(user?.gender || 'Not specified');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Reviews states
  const [rating, setRating] = useState<number>(5);
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [reviewText, setReviewText] = useState('');
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [existingReview, setExistingReview] = useState<ReviewItem | null>(null);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.push('/login?redirect=/dashboard');
      return;
    }

    Promise.all([
      getUserUsage(), 
      getUserConversions(),
      getUserProfile().catch(() => null),
      getMyReview().catch(() => null)
    ])
      .then(([u, c, prof, revData]) => {
        setUsage(u);
        setConversions(c);
        if (prof) {
          if (prof.full_name) setFullName(prof.full_name);
          if (prof.mobile_number) setMobileNumber(prof.mobile_number);
          if (prof.gender) setGender(prof.gender);
        }
        if (revData && revData.has_review && revData.review) {
          setExistingReview(revData.review);
          setRating(revData.review.rating);
          setReviewText(revData.review.review_text || '');
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [isLoading, isAuthenticated, router]);

  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMessage(null);
    setProfileError(null);

    const cleanMobile = mobileNumber.replace(/\D/g, '');
    if (cleanMobile && cleanMobile.length !== 10) {
      setProfileError('Mobile number must be exactly 10 digits.');
      setProfileSaving(false);
      return;
    }

    try {
      const res = await updateUserProfile({
        full_name: fullName.trim(),
        mobile_number: cleanMobile,
        gender: gender
      });
      if (res.success) {
        setProfileMessage('Profile details updated successfully!');
        setTimeout(() => setProfileMessage(null), 4000);
      }
    } catch (err: any) {
      setProfileError(err?.message || 'Failed to update profile. Please try again.');
    } finally {
      setProfileSaving(false);
    }
  };

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setReviewSubmitting(true);
    setReviewSuccess(null);
    setReviewError(null);

    try {
      const res = await submitReview({
        rating,
        review_text: reviewText.trim()
      });
      if (res.success) {
        setReviewSuccess('Thank you! Your rating and feedback have been submitted.');
        setExistingReview({
          id: res.review_id,
          user_name: fullName || 'Verified Customer',
          rating: res.rating,
          review_text: reviewText.trim(),
          created_at: new Date().toISOString()
        });
        setTimeout(() => setReviewSuccess(null), 5000);
      }
    } catch (err: any) {
      setReviewError(err?.message || 'Failed to submit review. Please try again.');
    } finally {
      setReviewSubmitting(false);
    }
  };

  const totalConversions = conversions.length;
  const successfulConversions = conversions.filter((c) => c.status === 'COMPLETED').length;
  const needsReviewConversions = conversions.filter((c) => c.status === 'NEEDS_REVIEW').length;
  const failedConversions = conversions.filter((c) => c.status === 'FAILED').length;

  const usedBills = usage?.bills_used_today ?? usage?.pages_used_today ?? 0;
  const dailyBillLimit = usage?.free_daily_bill_limit ?? 5;
  const remainingBills = usage?.is_unlimited ? 999999 : (usage?.bills_remaining_today ?? Math.max(0, dailyBillLimit - usedBills));
  const usagePercent = usage?.is_unlimited ? 100 : Math.min(100, Math.round((usedBills / dailyBillLimit) * 100));
  const additionalBalance = usage?.additional_bill_balance ?? usage?.additional_page_balance ?? 0;

  return (
    <div className="py-10 bg-slate-50 min-h-screen animate-fadeIn">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Top Header / Welcome Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-navy-900 text-white p-6 sm:p-7 rounded-3xl border border-navy-800 shadow-glow-brand relative overflow-hidden group">
          <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 rounded-full bg-brand-500/20 blur-3xl pointer-events-none transition-transform duration-700 group-hover:scale-110" />
          <div className="relative z-10 space-y-1">
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2">
                <span>Welcome, {fullName || user?.email?.split('@')[0]}</span>
                {isGold && <GoldTick size="md" />}
              </h1>
              {isStaff ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-extrabold bg-amber-400/20 text-amber-300 border border-amber-400/40">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  Staff Member — Unlimited
                  {isGold && <GoldTick size="sm" />}
                </span>
              ) : (
                <Badge variant={usage?.is_unlimited ? 'purple' : 'success'} size="sm">
                  {usage?.is_unlimited ? 'Unlimited Tier' : '5 Free Bills Daily'}
                </Badge>
              )}
            </div>
            <p className="text-xs text-navy-200">
              {isStaff ? (
                <span>You have unlimited bill conversions with zero daily limits and high-speed processing.</span>
              ) : (
                <span>
                  Daily quota resets automatically at midnight (12:00 AM IST) • Need unlimited bills?{' '}
                  <button
                    onClick={() => setShowSubModal(true)}
                    className="text-amber-400 hover:text-amber-300 font-bold underline cursor-pointer"
                  >
                    Upgrade to Verified
                  </button>
                </span>
              )}
            </p>
          </div>

          <div className="relative z-10 flex flex-wrap items-center gap-2.5">
            <Link href="/sales">
              <Button variant="primary" size="md" className="shadow-glow-brand font-bold" iconRight={<ArrowRight className="w-4 h-4" />}>
                Sales Invoice → XML
              </Button>
            </Link>
            <Link href="/purchase">
              <Button variant="outline-dark" size="md" className="bg-emerald-600/30 border-emerald-500/50 text-emerald-200 hover:text-white font-bold" iconRight={<ArrowRight className="w-4 h-4" />}>
                Purchase Invoice → XML
              </Button>
            </Link>
            <a href="https://kangrahubtallyxml.netlify.app/">
              <Button variant="dark" size="md" className="bg-navy-800 hover:bg-navy-700 text-slate-300 font-semibold" iconRight={<ArrowRight className="w-4 h-4" />}>
                Bank Import →
              </Button>
            </a>
          </div>
        </div>

        {/* 4 Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5 animate-slideUp">
          
          {/* Card 1: Today's Free Bills */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 relative overflow-hidden group bg-gradient-to-br from-white to-slate-50/50">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Today's Free Usage
                </span>
                <div className="mt-2 text-2xl font-black text-slate-900 tabular-nums">
                  {usage?.is_unlimited ? 'Unlimited' : `${usedBills} / ${dailyBillLimit} Bills`}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <Receipt className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100">
              {!usage?.is_unlimited && (
                <div className="w-full bg-slate-100 rounded-full h-2 mb-2 overflow-hidden shadow-inner">
                  <div
                    className="bg-brand-500 h-full rounded-full transition-all duration-1000 ease-out relative overflow-hidden"
                    style={{ width: `${usagePercent}%` }}
                  >
                    <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full animate-shimmer" />
                  </div>
                </div>
              )}
              <span className="text-[11px] text-slate-500">
                {usage?.is_unlimited ? 'Exempt from bill constraints' : `${remainingBills} free bills remaining today`}
              </span>
            </div>
          </Card>

          {/* Card 2: Remaining & Paid Balance */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 bg-gradient-to-br from-white to-slate-50/50 group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Remaining Allowance
                </span>
                <div className="mt-2 text-2xl font-black text-emerald-600 tabular-nums flex items-baseline flex-wrap gap-1">
                  <span>{usage?.is_unlimited ? '∞' : remainingBills}</span>
                  {additionalBalance > 0 ? (
                    <span className="text-xs text-accent-600 font-bold font-sans">
                      (+{additionalBalance} paid)
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <Sparkles className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
              {usage?.is_unlimited ? (isStaff ? 'Unlimited Staff quota' : 'Unlimited Admin quota') : 'Bills available to process today'}
            </div>
          </Card>

          {/* Card 3: Staff Membership Status */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 bg-gradient-to-br from-white to-slate-50/50 group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Membership Tier
                </span>
                <div className="mt-2 text-xl font-black text-slate-900 flex items-center gap-1.5">
                  {isStaff ? (
                    <>
                      <span className="text-amber-600">Staff Active</span>
                      {isGold && <GoldTick size="sm" />}
                    </>
                  ) : (
                    <span className="text-slate-700">Free Tier</span>
                  )}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-100/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <Sparkles className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
              {isStaff ? (
                <span className="text-emerald-600 font-semibold">Unlimited bill conversions</span>
              ) : (
                <button
                  onClick={() => setShowSubModal(true)}
                  className="text-amber-600 hover:text-amber-700 font-bold underline cursor-pointer"
                >
                  Upgrade to Staff (₹499/mo)
                </button>
              )}
            </div>
          </Card>

          {/* Card 4: Total Conversions */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 bg-gradient-to-br from-white to-slate-50/50 group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Total Conversions
                </span>
                <div className="mt-2 text-2xl font-black text-slate-900 tabular-nums">
                  {totalConversions}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center border border-slate-200/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <FileText className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] flex flex-wrap items-center gap-2">
              <span className="text-emerald-600 font-semibold">{successfulConversions} Successful</span>
              {failedConversions > 0 && (
                <>
                  <span className="text-slate-300">•</span>
                  <span className="text-rose-600 font-semibold">{failedConversions} Failed</span>
                </>
              )}
            </div>
          </Card>

        </div>

        {/* Recent Conversions Table Card */}
        <Card className="shadow-elevated overflow-hidden border-slate-200/80 animate-slideUp">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-slate-50/50 border-b border-slate-100">
            <div>
              <CardTitle className="text-lg">Recent Invoice Conversions</CardTitle>
              <CardDescription>
                Review and download your recent Sales & Purchase Tally XML vouchers
              </CardDescription>
            </div>
            <Link href="/history">
              <Button variant="ghost" size="sm" iconRight={<ChevronRight className="w-3.5 h-3.5" />}>
                View Complete History
              </Button>
            </Link>
          </CardHeader>

          {loading ? (
            <div className="p-8 space-y-4">
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-10 w-full rounded-xl" />
            </div>
          ) : conversions.length === 0 ? (
            <EmptyState
              icon={<Receipt className="w-8 h-8 text-brand-400" />}
              title="No invoices processed yet"
              description="Upload your first Sales or Purchase invoice PDF to extract line items and download balanced Tally XML."
              action={
                <div className="flex flex-wrap items-center justify-center gap-3">
                  <Link href="/sales">
                    <Button variant="primary" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                      Convert Sales Invoice
                    </Button>
                  </Link>
                  <Link href="/purchase">
                    <Button variant="outline" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                      Convert Purchase Invoice
                    </Button>
                  </Link>
                  <a href="https://kangrahubtallyxml.netlify.app/">
                    <Button variant="ghost" size="sm">
                      Bank Statement Import →
                    </Button>
                  </a>
                </div>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-slate-50/50">
                  <TableRow>
                    <TableHead className="w-[180px]">Date & Time</TableHead>
                    <TableHead>File / Batch Name</TableHead>
                    <TableHead>Invoice Type</TableHead>
                    <TableHead className="text-center">Bills Processed</TableHead>
                    <TableHead className="text-center">Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {conversions.slice(0, 10).map((c) => (
                    <TableRow key={c.id} className="hover:bg-slate-50/80 transition-colors">
                      <TableCell className="text-xs text-slate-500 font-mono">
                        {c.created_at ? new Date(c.created_at).toLocaleString('en-IN', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          hour12: true
                        }) : 'Recent'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Receipt className="w-4 h-4 text-brand-500 shrink-0" />
                          <span className="font-medium text-xs text-slate-900 truncate max-w-[220px]" title={c.file_name}>
                            {c.file_name || 'Invoice_Batch.pdf'}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="primary" size="sm">
                          {c.bank_name || 'Invoice'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center text-xs font-bold text-slate-700">
                        {c.pages_processed || 1} Bills
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant={c.status === 'COMPLETED' ? 'success' : c.status === 'FAILED' ? 'danger' : 'warning'} size="sm">
                          {c.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {c.status === 'COMPLETED' && (
                          <a
                            href={`/api/invoices/download/${c.id}`}
                            download={`${c.file_name?.replace(/\.[^/.]+$/, '') || 'Invoice'}_Tally.xml`}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-brand-600 hover:text-brand-700 hover:bg-brand-50 rounded-lg transition-colors"
                          >
                            <Download className="w-3.5 h-3.5" />
                            Download XML
                          </a>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </Card>

        {/* User Profile & Rating Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-slideUp">
          
          {/* Card: Account Profile Details */}
          <Card className="shadow-elevated border-slate-200/80 overflow-hidden">
            <CardHeader className="bg-slate-50/50 border-b border-slate-100 flex flex-row items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100">
                <User className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-lg font-bold text-slate-900">Account Profile</CardTitle>
                <CardDescription>
                  Manage your personal details and registered credentials
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              <form onSubmit={handleProfileSave} className="space-y-4">
                {profileMessage && (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
                    <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>{profileMessage}</span>
                  </div>
                )}
                {profileError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>{profileError}</span>
                  </div>
                )}

                {/* Email (Read-only identity) */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email Address <span className="text-[11px] text-slate-400 font-normal">(Permanent Identity)</span>
                  </label>
                  <div className="relative">
                    <input
                      type="email"
                      value={user?.email || ''}
                      disabled
                      className="w-full px-3.5 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-sm text-slate-600 cursor-not-allowed pr-28"
                    />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-md text-[11px] font-bold">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>Verified</span>
                    </div>
                  </div>
                </div>

                {/* Full Name */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Full Name
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Enter your full name"
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
                  />
                </div>

                {/* Mobile Number & Gender Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Mobile Number
                    </label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium text-xs">
                        +91
                      </div>
                      <input
                        type="tel"
                        maxLength={10}
                        value={mobileNumber}
                        onChange={(e) => setMobileNumber(e.target.value.replace(/\D/g, ''))}
                        placeholder="10-digit number"
                        className="w-full pl-11 pr-3.5 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Gender
                    </label>
                    <select
                      value={gender}
                      onChange={(e) => setGender(e.target.value)}
                      className="w-full px-3.5 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
                    >
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                      <option value="Prefer not to say">Prefer not to say</option>
                    </select>
                  </div>
                </div>

                <div className="pt-2">
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    disabled={profileSaving}
                    className="w-full sm:w-auto font-bold shadow-xs flex items-center justify-center gap-2"
                  >
                    {!profileSaving && <Save className="w-4 h-4" />}
                    <span>{profileSaving ? 'Saving Changes...' : 'Save Profile Details'}</span>
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Card: Rate Your Experience */}
          <Card className="shadow-elevated border-slate-200/80 overflow-hidden">
            <CardHeader className="bg-slate-50/50 border-b border-slate-100 flex flex-row items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-500 flex items-center justify-center border border-amber-100">
                <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
              </div>
              <div>
                <CardTitle className="text-lg font-bold text-slate-900">Rate Your Experience</CardTitle>
                <CardDescription>
                  Help us improve Sales & Purchase invoice conversions
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              <form onSubmit={handleReviewSubmit} className="space-y-4">
                {reviewSuccess && (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
                    <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>{reviewSuccess}</span>
                  </div>
                )}
                {reviewError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>{reviewError}</span>
                  </div>
                )}

                {/* 5-Star Rating Selector */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-2">
                    Overall Satisfaction Rating
                  </label>
                  <div className="flex items-center gap-2">
                    {[1, 2, 3, 4, 5].map((starValue) => {
                      const isActive = starValue <= (hoverRating || rating);
                      return (
                        <button
                          key={starValue}
                          type="button"
                          onClick={() => setRating(starValue)}
                          onMouseEnter={() => setHoverRating(starValue)}
                          onMouseLeave={() => setHoverRating(0)}
                          className="p-1 rounded-lg hover:scale-110 transition-transform focus:outline-none"
                          aria-label={`${starValue} Stars`}
                        >
                          <Star
                            className={`w-7 h-7 transition-colors ${
                              isActive
                                ? 'text-amber-400 fill-amber-400'
                                : 'text-slate-300'
                            }`}
                          />
                        </button>
                      );
                    })}
                    <span className="ml-2 text-xs font-bold text-slate-700">
                      {rating === 5 && '5/5 — Excellent ⭐'}
                      {rating === 4 && '4/5 — Very Good'}
                      {rating === 3 && '3/5 — Good'}
                      {rating === 2 && '2/5 — Fair'}
                      {rating === 1 && '1/5 — Needs Improvement'}
                    </span>
                  </div>
                </div>

                {/* Comments / Review Text */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Your Review & Suggestions <span className="text-[11px] text-slate-400 font-normal">(Optional)</span>
                  </label>
                  <textarea
                    rows={3}
                    value={reviewText}
                    onChange={(e) => setReviewText(e.target.value)}
                    placeholder="Share feedback on OCR accuracy, GST calculations, or suggestions for Tally XML export..."
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all resize-none"
                  />
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    disabled={reviewSubmitting}
                    className="font-bold shadow-xs flex items-center gap-1.5"
                  >
                    {!reviewSubmitting && <Star className="w-4 h-4 fill-current" />}
                    <span>{reviewSubmitting ? 'Submitting...' : existingReview ? 'Update My Review' : 'Submit Review'}</span>
                  </Button>
                  {existingReview && (
                    <span className="text-[11px] text-slate-500">
                      Last reviewed on {new Date(existingReview.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
                    </span>
                  )}
                </div>
              </form>
            </CardContent>
          </Card>

        </div>

      </div>

      <SubscriptionModal
        isOpen={showSubModal}
        onClose={() => setShowSubModal(false)}
        onSuccess={() => {
          getUserUsage().then(setUsage).catch(() => {});
        }}
      />
    </div>
  );
}
