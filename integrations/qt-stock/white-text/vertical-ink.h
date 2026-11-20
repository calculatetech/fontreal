struct StemSection {
    int y;
    double center;
    double mass;
};

#include "straight-italic.h"
#include "rounded-ink.h"

QByteArray strengthenItalicStems(std::vector<fontreal_v3::Coverage> &coverage,
                                const fontreal_v3::OutlineSamples &outline, fontreal_v3::Ink ink,
                                const QByteArray &crossbar, double italicSlope,
                                fontreal_v3::OutlineSamples *fitted, QByteArray &aligned, QByteArray &exactStems, int mode, QByteArray *savedJoins, bool useFontSlant)
{
    const int width = outline.frame.width, height = outline.frame.height;
    const int stride = 4;
    std::vector<std::vector<StemSection>> tracks;
    std::vector<std::size_t> preceding;
    for (int y=0; y<stride*height; ++y) {
        std::vector<std::size_t> current;
        for (int x=0; x<stride*width;) {
            if (outline.highPixel(x,y) < 69) {
                ++x;
                continue;
            }
            const int start=x;
            double mass=0, moment=0;
            while (x<stride*width && outline.highPixel(x,y)>=69) {
                const int value=outline.highPixel(x,y);
                mass += value;
                moment += (x+.5)*value;
                ++x;
            }
            if (mass < 330 || mass > 1570 || x-start > 7)
                continue;
            const StemSection row{y,moment/mass,mass};
            const auto neighbor=std::find_if(preceding.begin(),preceding.end(),[&](std::size_t index) {
                const auto &last=tracks[index].back();
                return last.y==y-1 && std::abs(last.center-row.center)<=1.12;
            });
            if (neighbor == preceding.end()) {
                current.push_back(tracks.size());
                tracks.push_back({row});
            } else {
                current.push_back(*neighbor);
                tracks[*neighbor].push_back(row);
            }
        }
        preceding=std::move(current);
    }

    const auto source=coverage;
    QByteArray selection(width*height,'\0');
    for (const auto &track : tracks) {
        const int range=track.back().y-track.front().y;
        if (range < 5)
            continue;
        const auto alignment = [&](const StemSection &first, const StemSection &last) {
            const double slope = (last.center-first.center)/(last.y-first.y);
            return std::clamp((.26-std::abs(slope-italicSlope))/.12,0.0,1.0);
        };
        const double wholeStem = alignment(track.front(), track.back());
        for (std::size_t start=0; start<track.size();) {
            const int row=track[start].y/stride;
            const auto begin=start;
            double inkMass=0, inkMoment=0;
            for (; start<track.size() && track[start].y/stride==row; ++start) {
                inkMass+=track[start].mass;
                inkMoment+=track[start].mass*track[start].center;
            }
            const auto count=start-begin;
            if (count<2)
                continue;
            const auto localStart = begin >= 2 ? begin - 2 : 0;
            const auto localEnd = std::min(track.size()-1, start+1);
            const double closeness = std::max(wholeStem, .85 * alignment(track[localStart], track[localEnd]));
            if (!closeness)
                continue;
            const int x=int(inkMoment/inkMass/stride);
            const int index=row*width+x;
            if (!crossbar.isEmpty() && crossbar[index])
                continue;
            const auto native=outline.center(x,row);
            const int before=source[index];
            if (before<46 || native<48)
                continue;
            const int target = ink == fontreal_v3::Ink::Dark ? 223 : 231;
            const double continuity=std::clamp((range-3)/8.0,.34,1.0);
            const double lift=std::clamp((target-before) * continuity * closeness * count/4.0,0.0, ink == fontreal_v3::Ink::Dark ? 72.0 : 56.0);
            const int raised=before+std::lround(lift);
            if (raised>coverage[index]) {
                coverage[index]=raised;
                selection[index]=char(255);
            }
        }
    }
    if (fitted) {
        if (savedJoins)
            *savedJoins=QByteArray(width*height,'\0');
        const auto guide=useFontSlant ? std::optional<double>{italicSlope} : std::nullopt;
        aligned=QByteArray(width*height,'\0');
        for (const auto &track: tracks) {
            const auto fit=measureStraightStem(track,italicSlope,false);
            if (fit) {
                alignStraightStem(track,*fit,coverage,outline,*fitted,ink,aligned,mode,savedJoins,guide);
                continue;
            }
            if (mode<7 || track.size()<16)
                continue;
            // A bend above a stem must not disqualify its straight lower section.
            for (std::size_t length=track.size()-1; length>=13; --length) {
                const std::vector<StemSection> tail(track.end()-length,track.end());
                const auto local=measureStraightStem(tail,italicSlope,true);
                if (local) {
                    alignStraightStem(tail,*local,coverage,outline,*fitted,ink,aligned,mode,savedJoins,guide);
                    break;
                }
            }
        }
    }
    exactStems=aligned;
    if (mode>=8 && fitted)
        restoreRoundEdges(coverage,outline,ink,aligned,mode);
    return selection;
}
